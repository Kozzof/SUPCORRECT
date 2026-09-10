USE supcorrect;

INSERT IGNORE INTO courses (id, code, label) VALUES
    (1, 'INIT', 'Initiation programmation');

INSERT IGNORE INTO exercises (id, course_id, number, title) VALUES
    (1, 1, 1, 'Somme de deux entiers'),
    (2, 1, 2, 'Maximum de trois entiers');

INSERT IGNORE INTO exercise_languages (exercise_id, language) VALUES
    (1, 'c'), (1, 'python'),
    (2, 'c'), (2, 'python');
