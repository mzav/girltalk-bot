import os
import sqlite3
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Optional
import json
import requests

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Configure logging with DEBUG level
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Constants
SCOPES = ['https://www.googleapis.com/auth/calendar']
DATABASE_FILE = 'girltalk_bot.db'
GOOGLE_CALENDAR_ON = True
# Get calendar ID from Replit Secrets
CALENDAR_ID = os.getenv('GOOGLE_CALENDAR_ID',
                        'primary')  # Use shared calendar ID from Secrets
# GOOGLE_CALENDAR_ON = os.getenv('GOOGLE_CALENDAR_ON', 'false').lower() == 'true'  # Feature toggle for Google Calendar


class GirlTalkBot:
    """
    Telegram bot for Girl Talk Community to manage meetings and events
    """

    def __init__(self):
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.calendar_service = None
        self.init_database()
        self.setup_google_calendar()

    def init_database(self):
        """Initialize SQLite database from schema file"""
        logger.debug(f"Initializing database: {DATABASE_FILE}")

        # Check if schema.sql exists
        if not os.path.exists('schema.sql'):
            logger.error("schema.sql file not found!")
            raise FileNotFoundError(
                "schema.sql is required for database initialization")

        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()

        # Read and execute schema from file
        logger.debug("Loading database schema from schema.sql")
        with open('schema.sql', 'r') as schema_file:
            schema_sql = schema_file.read()

        # Execute schema statements
        cursor.executescript(schema_sql)

        # Add calendar_link column if it doesn't exist (for existing databases migration)
        try:
            cursor.execute(
                'ALTER TABLE meetings ADD COLUMN calendar_link TEXT')
            logger.debug(
                "Added calendar_link column to existing meetings table")
        except sqlite3.OperationalError:
            # Column already exists
            pass

        conn.commit()
        conn.close()
        logger.info("Database initialized successfully from schema.sql")

    def setup_google_calendar(self):
        """Setup Google Calendar API service using service account"""
        logger.debug(
            f"Setting up Google Calendar (GOOGLE_CALENDAR_ON={GOOGLE_CALENDAR_ON})"
        )
        if not GOOGLE_CALENDAR_ON:
            self.calendar_service = None
            logger.info("Google Calendar integration DISABLED")
            return

        try:
            logger.debug("Checking for service account key file")
            if not os.path.exists('service-account-key.json'):
                logger.error(
                    "service-account-key.json not found. Please add Google service account credentials."
                )
                self.calendar_service = None
                return

            logger.debug("Loading service account credentials")
            creds = Credentials.from_service_account_file(
                'service-account-key.json', scopes=SCOPES)

            logger.debug("Building Calendar service")
            self.calendar_service = build('calendar', 'v3', credentials=creds)
            logger.info(
                "Google Calendar service initialized successfully with service account"
            )

        except Exception as e:
            logger.error(f"Error setting up Google Calendar: {e}")
            self.calendar_service = None

    async def start_command(self, update: Update,
                            context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user_id = update.effective_user.id
        username = update.effective_user.username or "Unknown"
        logger.info(f"User {user_id} (@{username}) started the bot")
        logger.debug(f"Processing /start command for user {user_id}")

        welcome_message = (
            "🌸 Welcome to GirlTalkBot! 🌸\n\n"
            "I help the Girl Talk Community manage meetings and events.\n\n"
            "Available commands:\n"
            "📅 /create_meeting - Create a new meeting\n"
            "📋 /upcoming_meetings - View all upcoming meetings\n"
            "📊 /my_meetings - View meetings you created\n"
            "❓ /help - Show this help message\n\n"
            "Let's make organizing events easier! ✨")

        # Create main menu keyboard
        keyboard = [[
            KeyboardButton("📅 Create Meeting"),
            KeyboardButton("📋 Upcoming Meetings")
        ], [KeyboardButton("📊 My Meetings"),
            KeyboardButton("❓ Help")]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        await update.message.reply_text(welcome_message,
                                        reply_markup=reply_markup)
        logger.debug(f"Sent welcome message to user {user_id}")

    async def help_command(self, update: Update,
                           context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_text = (
            "🌸 GirlTalkBot Help 🌸\n\n"
            "Commands:\n"
            "📅 /create_meeting - Create a new meeting\n"
            "📋 /upcoming_meetings - View all upcoming meetings\n"
            "📊 /my_meetings - View meetings you created\n"
            "🗑️ /delete_meeting <meeting_id> - Delete your meeting\n\n"
            "How to use:\n"
            "1. Create meetings with title, description, and date/time\n"
            "2. Other members can register for meetings\n"
            "3. View statistics and manage your meetings\n\n"
            "Need help? Contact the community admins! 💝")
        await update.message.reply_text(help_text)

    async def create_meeting_command(self, update: Update,
                                     context: ContextTypes.DEFAULT_TYPE):
        """Start the meeting creation process"""
        user_id = update.effective_user.id
        username = update.effective_user.username or "Unknown"
        logger.info(f"User {user_id} (@{username}) started creating a meeting")
        logger.debug(f"Initiating meeting creation flow for user {user_id}")

        await update.message.reply_text("📅 Let's create a new meeting!\n\n"
                                        "Please send me the meeting title:")
        context.user_data['creating_meeting'] = True
        context.user_data['meeting_step'] = 'title'
        logger.debug(
            f"Set meeting creation state for user {user_id}: step=title")

    async def handle_meeting_creation(self, update: Update,
                                      context: ContextTypes.DEFAULT_TYPE):
        """Handle meeting creation flow"""
        user_id = update.effective_user.id
        logger.debug(f"Processing meeting creation input from user {user_id}")

        if not context.user_data.get('creating_meeting'):
            logger.debug(
                f"User {user_id} not in meeting creation flow, ignoring")
            return

        step = context.user_data.get('meeting_step')
        logger.debug(f"User {user_id} in meeting creation step: {step}")

        if step == 'title':
            title = update.message.text
            logger.debug(f"User {user_id} provided meeting title: {title}")
            context.user_data['meeting_title'] = title
            context.user_data['meeting_step'] = 'description'
            await update.message.reply_text(
                f"✅ Title: {title}\n\n"
                "Now, please provide a description for the meeting:")
            logger.debug(f"Advanced user {user_id} to description step")

        elif step == 'description':
            description = update.message.text
            logger.debug(
                f"User {user_id} provided meeting description: {description}")
            context.user_data['meeting_description'] = description
            context.user_data['meeting_step'] = 'datetime'
            await update.message.reply_text(
                f"✅ Description: {description}\n\n"
                "Please provide the date and time for the meeting.\n"
                "Format: YYYY-MM-DD HH:MM\n"
                "Example: 2024-12-25 14:30")
            logger.debug(f"Advanced user {user_id} to datetime step")

        elif step == 'datetime':
            datetime_input = update.message.text
            logger.debug(
                f"User {user_id} provided meeting datetime: {datetime_input}")
            try:
                # Parse the datetime
                meeting_datetime = datetime.strptime(datetime_input,
                                                     "%Y-%m-%d %H:%M")
                logger.debug(
                    f"Parsed datetime for user {user_id}: {meeting_datetime}")

                # Check if the date is in the future
                if meeting_datetime <= datetime.now():
                    logger.debug(
                        f"User {user_id} provided past datetime, rejecting")
                    await update.message.reply_text(
                        "❌ Please provide a future date and time.\n"
                        "Format: YYYY-MM-DD HH:MM")
                    return

                # Create the meeting
                logger.info(
                    f"Creating meeting for user {user_id}: {context.user_data['meeting_title']}"
                )
                success, calendar_link = await self.create_calendar_event(
                    title=context.user_data['meeting_title'],
                    description=context.user_data['meeting_description'],
                    start_time=meeting_datetime,
                    creator_id=update.effective_user.id,
                    creator_username=update.effective_user.username
                    or "Unknown")

                if success:
                    logger.info(
                        f"Meeting created successfully for user {user_id}")

                    success_message = (
                        f"🎉 Meeting created successfully!\n\n"
                        f"📅 **{context.user_data['meeting_title']}**\n"
                        f"📝 {context.user_data['meeting_description']}\n"
                        f"🕐 {meeting_datetime.strftime('%Y-%m-%d at %H:%M')}\n\n"
                    )

                    if calendar_link:
                        success_message += f"📞 [Join Google Calendar Meeting]({calendar_link})\n\n"

                    success_message += "Your meeting has been added and members can now register! ✨"

                    await update.message.reply_text(
                        success_message,
                        parse_mode='Markdown',
                        disable_web_page_preview=True)
                else:
                    logger.error(
                        f"Failed to create meeting for user {user_id}")
                    await update.message.reply_text(
                        "❌ Sorry, there was an error creating the meeting. Please try again."
                    )

                # Reset creation state
                logger.debug(
                    f"Resetting meeting creation state for user {user_id}")
                context.user_data['creating_meeting'] = False
                context.user_data.pop('meeting_step', None)
                context.user_data.pop('meeting_title', None)
                context.user_data.pop('meeting_description', None)

            except ValueError as e:
                logger.debug(
                    f"User {user_id} provided invalid datetime format: {datetime_input}, error: {e}"
                )
                await update.message.reply_text(
                    "❌ Invalid date format. Please use: YYYY-MM-DD HH:MM\n"
                    "Example: 2024-12-25 14:30")

    async def create_calendar_event(self, title: str, description: str,
                                    start_time: datetime, creator_id: int,
                                    creator_username: str) -> tuple[bool, str]:
        """Create calendar event with optional Google Calendar integration"""
        try:
            # Create end time (1 hour after start)
            end_time = start_time + timedelta(hours=1)

            event_id = None
            calendar_link = None

            # Create Google Calendar event if enabled
            if GOOGLE_CALENDAR_ON and self.calendar_service:
                try:
                    event = {
                        'summary': title,
                        'description':
                        f"{description}\n\nCreated by: @{creator_username}",
                        'start': {
                            'dateTime': start_time.isoformat(),
                            'timeZone': 'UTC',
                        },
                        'end': {
                            'dateTime': end_time.isoformat(),
                            'timeZone': 'UTC',
                        },
                    }

                    created_event = self.calendar_service.events().insert(
                        calendarId=CALENDAR_ID, body=event).execute()

                    event_id = created_event['id']
                    calendar_link = created_event.get('htmlLink')
                    logger.info(f"Google Calendar event created: {event_id}")
                    logger.debug(f"Google Calendar link: {calendar_link}")

                except HttpError as e:
                    logger.error(f"Google Calendar API error: {e}")
                    # Continue with database-only storage
                except Exception as e:
                    logger.error(f"Error creating Google Calendar event: {e}")
                    # Continue with database-only storage

            # Generate fallback event ID if Google Calendar failed or is disabled
            if not event_id:
                event_id = f"local_event_{datetime.now().timestamp()}"
                if not GOOGLE_CALENDAR_ON:
                    logger.info(
                        f"Meeting created (Google Calendar disabled): {title}")
                else:
                    logger.info(
                        f"Meeting created (Google Calendar failed, using local storage): {title}"
                    )

            # Store in database (including calendar link)
            conn = sqlite3.connect(DATABASE_FILE)
            cursor = conn.cursor()

            cursor.execute(
                '''
                INSERT INTO meetings (event_id, creator_id, creator_username, title, description, start_time, end_time, calendar_link)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (event_id, creator_id, creator_username, title, description,
                  start_time.isoformat(), end_time.isoformat(), calendar_link))

            conn.commit()
            conn.close()

            return True, calendar_link

        except Exception as e:
            logger.error(f"Error creating meeting: {e}")
            return False, None

    async def upcoming_meetings_command(self, update: Update,
                                        context: ContextTypes.DEFAULT_TYPE):
        """Show all upcoming meetings"""
        user_id = update.effective_user.id
        username = update.effective_user.username or "Unknown"
        logger.info(
            f"User {user_id} (@{username}) requested upcoming meetings")

        meetings = self.get_upcoming_meetings()
        logger.debug(f"Found {len(meetings)} upcoming meetings")

        if not meetings:
            logger.debug(f"No upcoming meetings found for user {user_id}")
            await update.message.reply_text(
                "📅 No upcoming meetings scheduled.\n\n"
                "Be the first to create one! Use /create_meeting 🌸")
            return

        message = "📅 **Upcoming Meetings** 📅\n\n"

        for i, meeting in enumerate(meetings):
            # meeting columns: id, event_id, creator_id, creator_username, title, description, start_time, end_time, created_at
            meeting_id = meeting[0]
            logger.debug(
                f"Processing meeting {i+1}/{len(meetings)}: ID={meeting_id}, title={meeting[4]}"
            )

            registration_count = self.get_registration_count(meeting_id)
            start_time = datetime.fromisoformat(
                meeting[6])  # start_time is at index 6

            # Create registration button
            keyboard = [[
                InlineKeyboardButton(
                    f"✅ Register ({registration_count} registered)",
                    callback_data=f"register_{meeting_id}"),
                InlineKeyboardButton("📊 Stats",
                                     callback_data=f"stats_{meeting_id}")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            meeting_text = (
                f"🌸 **{meeting[4]}**\n"  # title is at index 4
                f"📝 {meeting[5]}\n"  # description is at index 5
                f"🕐 {start_time.strftime('%Y-%m-%d at %H:%M')}\n"
                f"👩‍💼 Created by: @{meeting[3]}\n"  # creator_username is at index 3
                f"👥 Registered: {registration_count} members\n")

            # Add calendar link if available (calendar_link is at index 8)
            if len(meeting) > 8 and meeting[8]:
                meeting_text += f"📞 [Join Meeting]({meeting[8]})\n"

            meeting_text += f"🆔 Meeting ID: {meeting_id}"

            await update.message.reply_text(meeting_text,
                                            reply_markup=reply_markup,
                                            parse_mode='Markdown',
                                            disable_web_page_preview=True)
            logger.debug(
                f"Sent meeting {meeting_id} details to user {user_id}")

    async def my_meetings_command(self, update: Update,
                                  context: ContextTypes.DEFAULT_TYPE):
        """Show meetings created by the user"""
        user_id = update.effective_user.id
        meetings = self.get_user_meetings(user_id)

        if not meetings:
            await update.message.reply_text(
                "📅 You haven't created any meetings yet.\n\n"
                "Create your first meeting with /create_meeting! 🌸")
            return

        message = "📊 **Your Meetings** 📊\n\n"

        for meeting in meetings:
            # meeting columns: id, event_id, creator_id, creator_username, title, description, start_time, end_time, created_at
            registration_count = self.get_registration_count(meeting[0])
            start_time = datetime.fromisoformat(
                meeting[6])  # start_time is at index 6

            keyboard = [[
                InlineKeyboardButton("📊 View Stats",
                                     callback_data=f"stats_{meeting[0]}"),
                InlineKeyboardButton("🗑️ Delete",
                                     callback_data=f"delete_{meeting[0]}")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            meeting_text = (
                f"🌸 **{meeting[4]}**\n"  # title is at index 4
                f"📝 {meeting[5]}\n"  # description is at index 5
                f"🕐 {start_time.strftime('%Y-%m-%d at %H:%M')}\n"
                f"👥 Registered: {registration_count} members\n")

            # Add calendar link if available (calendar_link is at index 8)
            if len(meeting) > 8 and meeting[8]:
                meeting_text += f"📞 [Join Meeting]({meeting[8]})\n"

            meeting_text += f"🆔 Meeting ID: {meeting[0]}"

            await update.message.reply_text(meeting_text,
                                            reply_markup=reply_markup,
                                            parse_mode='Markdown',
                                            disable_web_page_preview=True)

    async def handle_callback_query(self, update: Update,
                                    context: ContextTypes.DEFAULT_TYPE):
        """Handle inline keyboard button presses"""
        query = update.callback_query
        await query.answer()

        data = query.data
        user_id = update.effective_user.id
        username = update.effective_user.username or "Unknown"

        logger.info(f"User {user_id} (@{username}) clicked button: {data}")
        logger.debug(f"Processing callback query: {data}")

        if data.startswith("register_"):
            meeting_id = int(data.split("_")[1])
            logger.debug(
                f"User {user_id} attempting to register for meeting {meeting_id}"
            )
            success = self.register_user_for_meeting(meeting_id, user_id,
                                                     username)

            if success:
                logger.info(
                    f"User {user_id} successfully registered for meeting {meeting_id}"
                )
                registration_count = self.get_registration_count(meeting_id)
                await query.edit_message_reply_markup(
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton(
                            f"✅ Registered ({registration_count} registered)",
                            callback_data=f"registered_{meeting_id}"),
                        InlineKeyboardButton(
                            "📊 Stats", callback_data=f"stats_{meeting_id}")
                    ]]))
                await query.message.reply_text(
                    f"🎉 You're registered for the meeting! ✨\n"
                    f"Total registered: {registration_count} members")
            else:
                logger.debug(
                    f"User {user_id} already registered for meeting {meeting_id}"
                )
                await query.message.reply_text(
                    "ℹ️ You're already registered for this meeting!")

        elif data.startswith("stats_"):
            meeting_id = int(data.split("_")[1])
            logger.debug(
                f"User {user_id} requested stats for meeting {meeting_id}")
            await self.show_meeting_stats(query.message, meeting_id)

        elif data.startswith("delete_"):
            meeting_id = int(data.split("_")[1])
            logger.debug(
                f"User {user_id} attempting to delete meeting {meeting_id}")
            meeting = self.get_meeting_by_id(meeting_id)

            # meeting columns: id, event_id, creator_id, creator_username, title, description, start_time, end_time, created_at
            if meeting and meeting[2] == user_id:  # creator_id is at index 2
                logger.debug(
                    f"User {user_id} authorized to delete meeting {meeting_id}"
                )
                success = await self.delete_meeting(meeting_id, meeting[2])
                if success:
                    logger.info(
                        f"User {user_id} successfully deleted meeting {meeting_id}"
                    )
                    await query.edit_message_text(
                        "🗑️ Meeting deleted successfully!")
                else:
                    logger.error(
                        f"Failed to delete meeting {meeting_id} for user {user_id}"
                    )
                    await query.message.reply_text(
                        "❌ Error deleting meeting. Please try again.")
            else:
                logger.warning(
                    f"User {user_id} unauthorized to delete meeting {meeting_id}"
                )
                await query.message.reply_text(
                    "❌ You can only delete meetings you created.")

    async def show_meeting_stats(self, message, meeting_id: int):
        """Show detailed statistics for a meeting"""
        meeting = self.get_meeting_by_id(meeting_id)
        if not meeting:
            await message.reply_text("❌ Meeting not found.")
            return

        registrations = self.get_meeting_registrations(meeting_id)
        registration_count = len(registrations)

        # meeting columns: id, event_id, creator_id, creator_username, title, description, start_time, end_time, created_at
        start_time = datetime.fromisoformat(
            meeting[6])  # start_time is at index 6

        stats_text = (
            f"📊 Meeting Statistics 📊\n\n"
            f"🌸 {meeting[4]}\n"  # title is at index 4
            f"📝 {meeting[5]}\n"  # description is at index 5
            f"🕐 {start_time.strftime('%Y-%m-%d at %H:%M')}\n"
            f"👩‍💼 Created by: @{meeting[3] or 'Unknown'}\n"  # creator_username is at index 3
        )

        # Add calendar link if available (calendar_link is at index 8)
        if len(meeting) > 8 and meeting[8]:
            stats_text += f"📞 Join Meeting: {meeting[8]}\n"

        stats_text += (f"\n👥 Registration Stats:\n"
                       f"• Total registered: {registration_count} members\n\n")

        if registrations:
            stats_text += "📋 Registered Members:\n"
            for reg in registrations:
                reg_time = datetime.fromisoformat(reg[4])
                username = reg[3] or 'Unknown'
                stats_text += f"• @{username} (registered {reg_time.strftime('%m-%d %H:%M')})\n"

        await message.reply_text(stats_text, disable_web_page_preview=True)

    def get_upcoming_meetings(self) -> List:
        """Get all upcoming meetings from database"""
        logger.debug("Fetching upcoming meetings from database")
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()

        now = datetime.now().isoformat()
        logger.debug(f"Querying meetings after: {now}")
        cursor.execute(
            '''
            SELECT * FROM meetings 
            WHERE start_time > ? 
            ORDER BY start_time ASC
        ''', (now, ))

        meetings = cursor.fetchall()
        conn.close()
        logger.debug(f"Found {len(meetings)} upcoming meetings")
        return meetings

    def get_user_meetings(self, user_id: int) -> List:
        """Get meetings created by a specific user"""
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT * FROM meetings 
            WHERE creator_id = ? 
            ORDER BY start_time ASC
        ''', (user_id, ))

        meetings = cursor.fetchall()
        conn.close()
        return meetings

    def get_meeting_by_id(self, meeting_id: int):
        """Get meeting details by ID"""
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM meetings WHERE id = ?', (meeting_id, ))
        meeting = cursor.fetchone()
        conn.close()
        return meeting

    def get_registration_count(self, meeting_id: int) -> int:
        """Get number of registrations for a meeting"""
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()

        cursor.execute(
            'SELECT COUNT(*) FROM registrations WHERE meeting_id = ?',
            (meeting_id, ))
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def get_meeting_registrations(self, meeting_id: int) -> List:
        """Get all registrations for a meeting"""
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT * FROM registrations 
            WHERE meeting_id = ? 
            ORDER BY registered_at ASC
        ''', (meeting_id, ))

        registrations = cursor.fetchall()
        conn.close()
        return registrations

    def register_user_for_meeting(self, meeting_id: int, user_id: int,
                                  username: str) -> bool:
        """Register a user for a meeting"""
        logger.debug(
            f"Attempting to register user {user_id} (@{username}) for meeting {meeting_id}"
        )
        try:
            conn = sqlite3.connect(DATABASE_FILE)
            cursor = conn.cursor()

            cursor.execute(
                '''
                INSERT INTO registrations (meeting_id, user_id, username)
                VALUES (?, ?, ?)
            ''', (meeting_id, user_id, username))

            conn.commit()
            conn.close()
            logger.info(f"User {user_id} registered for meeting {meeting_id}")
            return True

        except sqlite3.IntegrityError as e:
            # User already registered
            logger.debug(
                f"User {user_id} already registered for meeting {meeting_id}: {e}"
            )
            return False
        except Exception as e:
            logger.error(
                f"Error registering user {user_id} for meeting {meeting_id}: {e}"
            )
            return False

    async def delete_meeting(self, meeting_id: int, creator_id: int) -> bool:
        """Delete a meeting and its registrations"""
        try:
            meeting = self.get_meeting_by_id(meeting_id)
            # meeting columns: id, event_id, creator_id, creator_username, title, description, start_time, end_time, created_at
            if not meeting or meeting[
                    2] != creator_id:  # creator_id is at index 2
                return False

            event_id = meeting[1]  # event_id is at index 1

            # Delete from Google Calendar if enabled and event exists there
            if GOOGLE_CALENDAR_ON and self.calendar_service and not event_id.startswith(
                    'local_event_'):
                try:
                    self.calendar_service.events().delete(
                        calendarId=CALENDAR_ID, eventId=event_id).execute()
                    logger.info(f"Google Calendar event deleted: {event_id}")
                except HttpError as e:
                    logger.error(
                        f"Google Calendar API error during deletion: {e}")
                    # Continue with database deletion even if Google Calendar fails
                except Exception as e:
                    logger.error(f"Error deleting Google Calendar event: {e}")
                    # Continue with database deletion even if Google Calendar fails
            else:
                if not GOOGLE_CALENDAR_ON:
                    logger.info(
                        f"Meeting deleted (Google Calendar disabled): {event_id}"
                    )
                else:
                    logger.info(f"Local meeting deleted: {event_id}")

            # Delete from database
            conn = sqlite3.connect(DATABASE_FILE)
            cursor = conn.cursor()

            # Delete registrations first
            cursor.execute('DELETE FROM registrations WHERE meeting_id = ?',
                           (meeting_id, ))

            # Delete meeting
            cursor.execute('DELETE FROM meetings WHERE id = ?', (meeting_id, ))

            conn.commit()
            conn.close()

            logger.info(f"Meeting {meeting_id} deleted successfully")
            return True

        except Exception as e:
            logger.error(f"Error deleting meeting: {e}")
            return False

    async def handle_keyboard_buttons(self, update: Update,
                                      context: ContextTypes.DEFAULT_TYPE):
        """Handle keyboard button presses"""
        text = update.message.text

        if text == "📅 Create Meeting":
            await self.create_meeting_command(update, context)
        elif text == "📋 Upcoming Meetings":
            await self.upcoming_meetings_command(update, context)
        elif text == "📊 My Meetings":
            await self.my_meetings_command(update, context)
        elif text == "❓ Help":
            await self.help_command(update, context)

    def run(self):
        """Start the bot"""
        logger.debug("Initializing bot startup")
        if not self.bot_token:
            logger.error("TELEGRAM_BOT_TOKEN environment variable not set")
            return

        logger.debug(f"Bot token loaded: {self.bot_token[:10]}...")

        # Create application
        logger.debug("Creating Telegram application")
        application = Application.builder().token(self.bot_token).build()

        # Add handlers
        logger.debug("Adding command handlers")
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(
            CommandHandler("create_meeting", self.create_meeting_command))
        application.add_handler(
            CommandHandler("upcoming_meetings",
                           self.upcoming_meetings_command))
        application.add_handler(
            CommandHandler("my_meetings", self.my_meetings_command))

        # Handle callback queries (inline buttons)
        logger.debug("Adding callback query handler")
        application.add_handler(
            CallbackQueryHandler(self.handle_callback_query))

        # Handle keyboard buttons
        logger.debug("Adding keyboard button handler")
        application.add_handler(
            MessageHandler(
                filters.Regex(
                    "^(📅 Create Meeting|📋 Upcoming Meetings|📊 My Meetings|❓ Help)$"
                ), self.handle_keyboard_buttons))

        # Handle meeting creation flow
        logger.debug("Adding meeting creation handler")
        application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND,
                           self.handle_meeting_creation))

        # Start the bot
        logger.info("Starting GirlTalkBot...")
        logger.debug("Starting polling for updates")
        application.run_polling()


def main():
    """Main function to run the bot"""
    logger.info("🌸 Starting GirlTalkBot application 🌸")
    logger.debug(f"Google Calendar feature toggle: {GOOGLE_CALENDAR_ON}")
    logger.debug(f"Database file: {DATABASE_FILE}")

    try:
        bot = GirlTalkBot()
        bot.run()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error starting bot: {e}")
        raise


if __name__ == '__main__':
    main()
