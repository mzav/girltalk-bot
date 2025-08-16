
-- GirlTalkBot Database Schema
-- This file contains the database structure for the Telegram bot

-- Meetings table to store meeting information
CREATE TABLE IF NOT EXISTS meetings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT UNIQUE,
    creator_id INTEGER,
    creator_username TEXT,
    title TEXT,
    description TEXT,
    start_time TEXT,
    end_time TEXT,
    calendar_link TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Registrations table to store user registrations for meetings
CREATE TABLE IF NOT EXISTS registrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id INTEGER,
    user_id INTEGER,
    username TEXT,
    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (meeting_id) REFERENCES meetings (id),
    UNIQUE(meeting_id, user_id)
);

-- Indexes for better performance
CREATE INDEX IF NOT EXISTS idx_meetings_start_time ON meetings(start_time);
CREATE INDEX IF NOT EXISTS idx_meetings_creator_id ON meetings(creator_id);
CREATE INDEX IF NOT EXISTS idx_registrations_meeting_id ON registrations(meeting_id);
CREATE INDEX IF NOT EXISTS idx_registrations_user_id ON registrations(user_id);

-- Test data insertion
-- Insert sample meetings (only if no data exists)
INSERT OR IGNORE INTO meetings (id, event_id, creator_id, creator_username, title, description, start_time, end_time, calendar_link, created_at) VALUES
(1, 'test_event_1', 123456789, 'alice_community', 'Welcome Coffee Chat', 'Join us for a casual coffee chat to welcome new members to the Girl Talk Community!', '2025-08-20 14:00:00', '2025-08-20 15:00:00', 'https://calendar.google.com/event?test=1', '2025-08-16 10:00:00'),
(2, 'test_event_2', 987654321, 'sarah_leader', 'Monthly Book Club Discussion', 'This month we are discussing "Becoming" by Michelle Obama. Come prepared with your thoughts!', '2025-08-25 18:30:00', '2025-08-25 20:00:00', 'https://calendar.google.com/event?test=2', '2025-08-16 11:00:00'),
(3, 'test_event_3', 456789123, 'emma_organizer', 'Career Development Workshop', 'Interactive workshop on resume building and interview preparation for professional growth.', '2025-08-30 16:00:00', '2025-08-30 17:30:00', 'https://calendar.google.com/event?test=3', '2025-08-16 12:00:00'),
(4, 'test_event_4', 789123456, 'maria_host', 'Wellness Wednesday Yoga', 'Relaxing yoga session to destress and connect with fellow community members.', '2025-09-05 19:00:00', '2025-09-05 20:00:00', 'https://calendar.google.com/event?test=4', '2025-08-16 13:00:00'),
(5, 'test_event_5', 321654987, 'jennifer_mentor', 'Entrepreneurship Panel', 'Panel discussion with successful female entrepreneurs sharing their journey and tips.', '2025-09-10 17:00:00', '2025-09-10 18:30:00', 'https://calendar.google.com/event?test=5', '2025-08-16 14:00:00');

-- Insert sample registrations for the meetings
INSERT OR IGNORE INTO registrations (meeting_id, user_id, username, registered_at) VALUES
-- Coffee Chat registrations
(1, 111222333, 'jessica_newbie', '2025-08-16 15:00:00'),
(1, 444555666, 'lisa_student', '2025-08-16 16:30:00'),
(1, 777888999, 'anna_professional', '2025-08-16 17:45:00'),

-- Book Club registrations
(2, 111222333, 'jessica_newbie', '2025-08-17 09:00:00'),
(2, 555666777, 'rachel_reader', '2025-08-17 12:15:00'),
(2, 888999111, 'sophia_bookworm', '2025-08-17 14:20:00'),
(2, 222333444, 'victoria_writer', '2025-08-17 18:00:00'),

-- Career Workshop registrations
(3, 444555666, 'lisa_student', '2025-08-18 10:30:00'),
(3, 777888999, 'anna_professional', '2025-08-18 13:45:00'),
(3, 999111222, 'michelle_jobseeker', '2025-08-18 16:00:00'),

-- Yoga registrations
(4, 111222333, 'jessica_newbie', '2025-08-19 08:00:00'),
(4, 555666777, 'rachel_reader', '2025-08-19 11:30:00'),

-- Entrepreneurship Panel registrations
(5, 777888999, 'anna_professional', '2025-08-20 09:15:00'),
(5, 999111222, 'michelle_jobseeker', '2025-08-20 14:30:00'),
(5, 333444555, 'diana_startup', '2025-08-20 16:45:00'),
(5, 666777888, 'caroline_founder', '2025-08-20 19:20:00');
