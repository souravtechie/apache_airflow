
TRUNCATE TABLE techtalksourav.videos_clean;

INSERT INTO techtalksourav.videos_clean
SELECT video_id,
       title,
       description,
       created_date,
       views,
       comments,
       likes,
       author
FROM (SELECT *,
             row_number() OVER (PARTITION BY video_id ORDER BY created_date DESC) row_num
      FROM techtalksourav.videos) de_duped
WHERE row_num = 1
;