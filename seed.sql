-- =====================================================
-- PAGETURNER BOOKS - SEED DATA
-- =====================================================

INSERT INTO books
(title, author, category, price, stock, description, cover_image)
VALUES
(
    'Atomic Habits',
    'James Clear',
    'Self Help',
    499,
    10,
    'A practical guide to building good habits and breaking bad ones.',
    'atomic-habits.jpg'
),

(
    'Deep Work',
    'Cal Newport',
    'Productivity',
    450,
    8,
    'Rules for focused success in a distracted world.',
    'deep-work.jpg'
),

(
    'The 7 Habits of Highly Effective People',
    'Stephen R. Covey',
    'Self Help',
    599,
    7,
    'A guide to personal and professional effectiveness.',
    '7-habits.jpg'
),

(
    'Think and Grow Rich',
    'Napoleon Hill',
    'Personal Development',
    399,
    9,
    'Classic principles for developing a success-oriented mindset.',
    'think-and-grow-rich.jpg'
),

(
    'Ikigai',
    'Héctor García',
    'Lifestyle',
    350,
    12,
    'A look at the Japanese concept of finding purpose and meaning.',
    'ikigai.jpg'
),

(
    'Clean Code',
    'Robert C. Martin',
    'Programming',
    699,
    6,
    'A guide to writing readable, maintainable and professional code.',
    'clean-code.jpg'
),

(
    'Python Crash Course',
    'Eric Matthes',
    'Programming',
    799,
    5,
    'A hands-on introduction to Python programming.',
    'python-crash-course.jpg'
),

(
    'The Pragmatic Programmer',
    'Andrew Hunt',
    'Programming',
    650,
    7,
    'Practical advice for becoming a better software developer.',
    'pragmatic-programmer.jpg'
),

(
    'A Brief History of Time',
    'Stephen Hawking',
    'Science',
    550,
    8,
    'An introduction to the universe, cosmology and modern physics.',
    'brief-history-of-time.jpg'
),

(
    'The Selfish Gene',
    'Richard Dawkins',
    'Science',
    620,
    6,
    'An exploration of evolution from the perspective of genes.',
    'selfish-gene.jpg'
),

(
    'Sapiens',
    'Yuval Noah Harari',
    'History',
    699,
    10,
    'A broad history of humankind and the development of human societies.',
    'sapiens.jpg'
),

(
    'India After Gandhi',
    'Ramachandra Guha',
    'History',
    799,
    5,
    'A detailed history of India after independence.',
    'india-after-gandhi.jpg'
),

(
    'The Alchemist',
    'Paulo Coelho',
    'Fiction',
    399,
    15,
    'A young shepherd follows his dreams and searches for his destiny.',
    'the-alchemist.jpg'
),

(
    'Rich Dad Poor Dad',
    'Robert T. Kiyosaki',
    'Finance',
    499,
    10,
    'Lessons about money, investing and financial independence.',
    'rich-dad-poor-dad.jpg'
);


-- =====================================================
-- SAMPLE COUPONS
-- =====================================================

INSERT OR IGNORE INTO coupons
(code, percent, expiry_date, active)
VALUES
(
    'WELCOME10',
    10,
    '2099-12-31',
    1
);

INSERT OR IGNORE INTO coupons
(code, percent, expiry_date, active)
VALUES
(
    'BOOK20',
    20,
    '2099-12-31',
    1
);