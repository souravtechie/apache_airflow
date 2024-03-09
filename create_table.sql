CREATE SCHEMA techtalksourav;

DROP TABLE IF EXISTS techtalksourav.video_details;

CREATE TABLE techtalksourav.video_details(
      video_id text,
      title text,
      publish_date timestamp,
      load_timestamp timestamp,
      view_count numeric,
      like_count numeric,
      comment_count numeric
)
;

SELECT *
FROM techtalksourav.video_details
;



















SELECT *
FROM information_schema.sql_features;



CREATE SCHEMA IF NOT EXISTS dummy_test;
CREATE TABLE IF NOT EXISTS dummy_test.load_test (A varchar, B int)
;


CREATE SCHEMA techtalksourav;

CREATE TABLE techtalksourav.videos(
      video_id numeric,
      title text,
      description text,
      created_date date,
      views numeric,
      comments numeric,
      likes numeric,
      author text
)
;




SELECT *
FROM techtalksourav.videos
;





