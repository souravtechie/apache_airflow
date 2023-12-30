

CREATE SCHEMA youtube;

CREATE TABLE youtube.video_details (
    video_id VARCHAR(255),
    view_count INT,
    like_count INT,
    comment_count INT
);

DROP TABLE IF EXISTS public.video_details;
CREATE TABLE public.video_details (
    video_id VARCHAR(255),
    view_count VARCHAR(255),
    like_count VARCHAR(255),
    load_timestamp VARCHAR(255),
    comment_count VARCHAR(255)
);

SELECT * FROM public.video_details;