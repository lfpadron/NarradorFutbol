"""DuckDB schema and analytical views for the StatsBomb analytics database."""

from __future__ import annotations

import duckdb

TABLE_COLUMNS: dict[str, list[str]] = {
    "competition": [
        "competition_id",
        "competition_name",
        "country_name",
        "competition_gender",
        "competition_youth",
        "competition_international",
    ],
    "season": ["season_id", "season_name", "competition_id"],
    "match": [
        "match_id",
        "competition_id",
        "season_id",
        "match_date",
        "kick_off",
        "home_team_id",
        "home_team_name",
        "away_team_id",
        "away_team_name",
        "home_score",
        "away_score",
        "stadium_name",
        "referee_name",
        "match_status",
        "data_version",
    ],
    "team": ["team_id", "team_name", "country_name"],
    "player": ["player_id", "player_name", "nickname", "country_name"],
    "lineup": [
        "match_id",
        "team_id",
        "team_name",
        "player_id",
        "player_name",
        "jersey_number",
        "position_name",
        "starter",
    ],
    "event": [
        "event_id",
        "match_id",
        "event_index",
        "period",
        "timestamp",
        "minute",
        "second",
        "type_id",
        "type_name",
        "possession",
        "possession_team_id",
        "possession_team_name",
        "team_id",
        "team_name",
        "player_id",
        "player_name",
        "position_id",
        "position_name",
        "play_pattern_id",
        "play_pattern_name",
        "duration",
        "location_x",
        "location_y",
        "under_pressure",
        "off_camera",
        "out",
        "raw_event_json",
    ],
    "pass": [
        "event_id",
        "match_id",
        "recipient_player_id",
        "recipient_player_name",
        "pass_length",
        "pass_angle",
        "pass_height_id",
        "pass_height_name",
        "pass_type_id",
        "pass_type_name",
        "pass_body_part_id",
        "pass_body_part_name",
        "pass_outcome_id",
        "pass_outcome_name",
        "pass_technique_id",
        "pass_technique_name",
        "pass_end_x",
        "pass_end_y",
        "pass_cross",
        "pass_switch",
        "pass_shot_assist",
        "pass_goal_assist",
        "pass_through_ball",
    ],
    "shot": [
        "event_id",
        "match_id",
        "shot_statsbomb_xg",
        "shot_outcome_id",
        "shot_outcome_name",
        "shot_body_part_id",
        "shot_body_part_name",
        "shot_technique_id",
        "shot_technique_name",
        "shot_type_id",
        "shot_type_name",
        "shot_end_x",
        "shot_end_y",
        "shot_end_z",
        "shot_first_time",
        "shot_one_on_one",
        "shot_key_pass_id",
    ],
    "carry": ["event_id", "match_id", "carry_end_x", "carry_end_y", "carry_distance"],
    "duel": ["event_id", "match_id", "duel_type_id", "duel_type_name", "duel_outcome_id", "duel_outcome_name"],
    "pressure": ["event_id", "match_id", "counterpress"],
    "foul": ["event_id", "match_id", "foul_type", "advantage", "offensive", "defensive", "card_id", "card_name"],
    "goalkeeper_action": [
        "event_id",
        "match_id",
        "goalkeeper_type_id",
        "goalkeeper_type_name",
        "goalkeeper_outcome_id",
        "goalkeeper_outcome_name",
        "goalkeeper_position_id",
        "goalkeeper_position_name",
        "goalkeeper_technique_id",
        "goalkeeper_technique_name",
        "goalkeeper_body_part_id",
        "goalkeeper_body_part_name",
        "goalkeeper_end_x",
        "goalkeeper_end_y",
    ],
    "substitution": [
        "event_id",
        "match_id",
        "replacement_player_id",
        "replacement_player_name",
        "substitution_outcome_id",
        "substitution_outcome_name",
    ],
    "event_relationship": ["source_event_id", "related_event_id", "match_id", "relationship_type"],
    "freeze_frame": [
        "event_id",
        "match_id",
        "player_id",
        "player_name",
        "teammate",
        "actor",
        "keeper",
        "location_x",
        "location_y",
    ],
    "visible_area": ["event_id", "match_id", "visible_area_json"],
    "transformation_log": [
        "match_id",
        "events_transformed",
        "events_rows",
        "passes_rows",
        "shots_rows",
        "lineups_rows",
        "freeze_frame_rows",
        "status",
        "transformed_at",
        "error_message",
    ],
}


def create_schema(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute("""
        CREATE TABLE IF NOT EXISTS competition (
            competition_id BIGINT PRIMARY KEY,
            competition_name VARCHAR,
            country_name VARCHAR,
            competition_gender VARCHAR,
            competition_youth BOOLEAN,
            competition_international BOOLEAN
        )
        """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS season (
            season_id BIGINT,
            season_name VARCHAR,
            competition_id BIGINT
        )
        """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS "match" (
            match_id BIGINT PRIMARY KEY,
            competition_id BIGINT,
            season_id BIGINT,
            match_date VARCHAR,
            kick_off VARCHAR,
            home_team_id BIGINT,
            home_team_name VARCHAR,
            away_team_id BIGINT,
            away_team_name VARCHAR,
            home_score BIGINT,
            away_score BIGINT,
            stadium_name VARCHAR,
            referee_name VARCHAR,
            match_status VARCHAR,
            data_version VARCHAR
        )
        """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS team (
            team_id BIGINT PRIMARY KEY,
            team_name VARCHAR,
            country_name VARCHAR
        )
        """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS player (
            player_id BIGINT PRIMARY KEY,
            player_name VARCHAR,
            nickname VARCHAR,
            country_name VARCHAR
        )
        """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS lineup (
            match_id BIGINT,
            team_id BIGINT,
            team_name VARCHAR,
            player_id BIGINT,
            player_name VARCHAR,
            jersey_number BIGINT,
            position_name VARCHAR,
            starter BOOLEAN
        )
        """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS event (
            event_id VARCHAR PRIMARY KEY,
            match_id BIGINT,
            event_index BIGINT,
            period BIGINT,
            timestamp VARCHAR,
            minute BIGINT,
            second BIGINT,
            type_id BIGINT,
            type_name VARCHAR,
            possession BIGINT,
            possession_team_id BIGINT,
            possession_team_name VARCHAR,
            team_id BIGINT,
            team_name VARCHAR,
            player_id BIGINT,
            player_name VARCHAR,
            position_id BIGINT,
            position_name VARCHAR,
            play_pattern_id BIGINT,
            play_pattern_name VARCHAR,
            duration DOUBLE,
            location_x DOUBLE,
            location_y DOUBLE,
            under_pressure BOOLEAN,
            off_camera BOOLEAN,
            out BOOLEAN,
            raw_event_json VARCHAR
        )
        """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS "pass" (
            event_id VARCHAR,
            match_id BIGINT,
            recipient_player_id BIGINT,
            recipient_player_name VARCHAR,
            pass_length DOUBLE,
            pass_angle DOUBLE,
            pass_height_id BIGINT,
            pass_height_name VARCHAR,
            pass_type_id BIGINT,
            pass_type_name VARCHAR,
            pass_body_part_id BIGINT,
            pass_body_part_name VARCHAR,
            pass_outcome_id BIGINT,
            pass_outcome_name VARCHAR,
            pass_technique_id BIGINT,
            pass_technique_name VARCHAR,
            pass_end_x DOUBLE,
            pass_end_y DOUBLE,
            pass_cross BOOLEAN,
            pass_switch BOOLEAN,
            pass_shot_assist BOOLEAN,
            pass_goal_assist BOOLEAN,
            pass_through_ball BOOLEAN
        )
        """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS shot (
            event_id VARCHAR,
            match_id BIGINT,
            shot_statsbomb_xg DOUBLE,
            shot_outcome_id BIGINT,
            shot_outcome_name VARCHAR,
            shot_body_part_id BIGINT,
            shot_body_part_name VARCHAR,
            shot_technique_id BIGINT,
            shot_technique_name VARCHAR,
            shot_type_id BIGINT,
            shot_type_name VARCHAR,
            shot_end_x DOUBLE,
            shot_end_y DOUBLE,
            shot_end_z DOUBLE,
            shot_first_time BOOLEAN,
            shot_one_on_one BOOLEAN,
            shot_key_pass_id VARCHAR
        )
        """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS carry (
            event_id VARCHAR,
            match_id BIGINT,
            carry_end_x DOUBLE,
            carry_end_y DOUBLE,
            carry_distance DOUBLE
        )
        """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS duel (
            event_id VARCHAR,
            match_id BIGINT,
            duel_type_id BIGINT,
            duel_type_name VARCHAR,
            duel_outcome_id BIGINT,
            duel_outcome_name VARCHAR
        )
        """)
    connection.execute("CREATE TABLE IF NOT EXISTS pressure (event_id VARCHAR, match_id BIGINT, counterpress BOOLEAN)")
    connection.execute("""
        CREATE TABLE IF NOT EXISTS foul (
            event_id VARCHAR,
            match_id BIGINT,
            foul_type VARCHAR,
            advantage BOOLEAN,
            offensive BOOLEAN,
            defensive BOOLEAN,
            card_id BIGINT,
            card_name VARCHAR
        )
        """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS goalkeeper_action (
            event_id VARCHAR,
            match_id BIGINT,
            goalkeeper_type_id BIGINT,
            goalkeeper_type_name VARCHAR,
            goalkeeper_outcome_id BIGINT,
            goalkeeper_outcome_name VARCHAR,
            goalkeeper_position_id BIGINT,
            goalkeeper_position_name VARCHAR,
            goalkeeper_technique_id BIGINT,
            goalkeeper_technique_name VARCHAR,
            goalkeeper_body_part_id BIGINT,
            goalkeeper_body_part_name VARCHAR,
            goalkeeper_end_x DOUBLE,
            goalkeeper_end_y DOUBLE
        )
        """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS substitution (
            event_id VARCHAR,
            match_id BIGINT,
            replacement_player_id BIGINT,
            replacement_player_name VARCHAR,
            substitution_outcome_id BIGINT,
            substitution_outcome_name VARCHAR
        )
        """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS event_relationship (
            source_event_id VARCHAR,
            related_event_id VARCHAR,
            match_id BIGINT,
            relationship_type VARCHAR
        )
        """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS freeze_frame (
            event_id VARCHAR,
            match_id BIGINT,
            player_id BIGINT,
            player_name VARCHAR,
            teammate BOOLEAN,
            actor BOOLEAN,
            keeper BOOLEAN,
            location_x DOUBLE,
            location_y DOUBLE
        )
        """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS visible_area (
            event_id VARCHAR,
            match_id BIGINT,
            visible_area_json VARCHAR
        )
        """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS transformation_log (
            match_id BIGINT PRIMARY KEY,
            events_transformed BOOLEAN,
            events_rows BIGINT,
            passes_rows BIGINT,
            shots_rows BIGINT,
            lineups_rows BIGINT,
            freeze_frame_rows BIGINT,
            status VARCHAR,
            transformed_at TIMESTAMP,
            error_message VARCHAR
        )
        """)


def create_views(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute("""
        CREATE OR REPLACE VIEW vw_match_summary AS
        WITH event_counts AS (
            SELECT match_id, COUNT(*) AS total_events
            FROM event
            GROUP BY match_id
        ),
        shot_counts AS (
            SELECT
                match_id,
                COUNT(*) AS total_shots,
                SUM(CASE WHEN shot_outcome_name = 'Goal' THEN 1 ELSE 0 END) AS total_goals,
                SUM(COALESCE(shot_statsbomb_xg, 0)) AS total_xg
            FROM shot
            GROUP BY match_id
        ),
        pass_counts AS (
            SELECT match_id, COUNT(*) AS total_passes
            FROM "pass"
            GROUP BY match_id
        )
        SELECT
            m.match_id,
            m.competition_id,
            m.season_id,
            m.match_date,
            m.home_team_name,
            m.away_team_name,
            m.home_score,
            m.away_score,
            COALESCE(e.total_events, 0) AS total_events,
            COALESCE(s.total_shots, 0) AS total_shots,
            COALESCE(s.total_goals, 0) AS total_goals,
            COALESCE(p.total_passes, 0) AS total_passes,
            COALESCE(s.total_xg, 0) AS total_xg
        FROM "match" m
        LEFT JOIN event_counts e ON e.match_id = m.match_id
        LEFT JOIN shot_counts s ON s.match_id = m.match_id
        LEFT JOIN pass_counts p ON p.match_id = m.match_id
        """)
    connection.execute("""
        CREATE OR REPLACE VIEW vw_shots AS
        SELECT e.*, s.* EXCLUDE (event_id, match_id)
        FROM event e
        INNER JOIN shot s ON s.event_id = e.event_id
        """)
    connection.execute("""
        CREATE OR REPLACE VIEW vw_goals AS
        SELECT *
        FROM vw_shots
        WHERE shot_outcome_name = 'Goal'
        """)
    connection.execute("""
        CREATE OR REPLACE VIEW vw_passes AS
        SELECT e.*, p.* EXCLUDE (event_id, match_id)
        FROM event e
        INNER JOIN "pass" p ON p.event_id = e.event_id
        """)
    connection.execute("""
        CREATE OR REPLACE VIEW vw_team_event_counts AS
        SELECT match_id, team_id, team_name, type_id, type_name, COUNT(*) AS events_count
        FROM event
        GROUP BY match_id, team_id, team_name, type_id, type_name
        """)
    connection.execute("""
        CREATE OR REPLACE VIEW vw_player_event_counts AS
        SELECT match_id, player_id, player_name, type_id, type_name, COUNT(*) AS events_count
        FROM event
        WHERE player_id IS NOT NULL
        GROUP BY match_id, player_id, player_name, type_id, type_name
        """)
    connection.execute("""
        CREATE OR REPLACE VIEW vw_ai_match_context AS
        SELECT
            match_id,
            home_team_name,
            away_team_name,
            home_score,
            away_score,
            total_events,
            total_shots,
            total_goals,
            total_passes,
            total_xg
        FROM vw_match_summary
        """)
