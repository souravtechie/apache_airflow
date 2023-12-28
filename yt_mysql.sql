

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
    viewCount VARCHAR(255),
    likeCount VARCHAR(255),
    commentCount VARCHAR(255)
);

SELECT * FROM public.video_details;