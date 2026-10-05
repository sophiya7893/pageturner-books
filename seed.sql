DELETE FROM reviews;
DELETE FROM order_items;
DELETE FROM orders;
DELETE FROM books;

INSERT INTO books
(title, author, category, price, description, stock, cover_color, cover_image)
VALUES
('Atomic Habits', 'James Clear', 'Self Help', 499,
'A practical guide to building good habits and breaking bad ones.',
10, '#d8b08c', 'atomic-habits.jpg'),

('Deep Work', 'Cal Newport', 'Productivity', 450,
'Rules for focused success in a distracted world.',
8, '#6f7d8c', 'deep-work.jpg'),

('The 7 Habits of Highly Effective People',
'Stephen R. Covey', 'Self Help', 599,
'A classic guide to personal effectiveness and leadership.',
7, '#b79b72', '7-habits.jpg'),

('Think and Grow Rich', 'Napoleon Hill',
'Personal Development', 399,
'A classic book about mindset, success and achievement.',
9, '#c9a66b', 'think-and-grow-rich.jpg'),

('Ikigai', 'Héctor García', 'Lifestyle', 350,
'A guide to finding purpose, balance and meaning.',
6, '#d98f83', 'ikigai.jpg'),

('Clean Code', 'Robert C. Martin',
'Programming', 699,
'A practical guide to writing readable and maintainable code.',
5, '#7c8fa6', 'clean-code.jpg'),

('Python Crash Course', 'Eric Matthes',
'Programming', 799,
'A hands-on introduction to Python programming.',
8, '#5d86a8', 'python-crash-course.jpg'),

('The Pragmatic Programmer', 'Andrew Hunt',
'Programming', 650,
'Practical advice for becoming a better programmer.',
4, '#806b91', 'pragmatic-programmer.jpg'),

('A Brief History of Time', 'Stephen Hawking',
'Science', 550,
'An accessible introduction to the mysteries of the universe.',
6, '#536b83', 'brief-history-of-time.jpg'),

('The Selfish Gene', 'Richard Dawkins',
'Science', 620,
'A fascinating exploration of evolution and genetics.',
5, '#8c7461', 'selfish-gene.jpg'),

('Sapiens', 'Yuval Noah Harari',
'History', 699,
'A broad history of humankind and civilization.',
7, '#9b8066', 'sapiens.jpg'),

('India After Gandhi', 'Ramachandra Guha',
'History', 799,
'A detailed history of India after independence.',
4, '#746b5c', 'india-after-gandhi.jpg'),

('The Alchemist', 'Paulo Coelho',
'Fiction', 399,
'A story about dreams, courage and following your journey.',
8, '#b98b62', 'the-alchemist.jpg'),

('Rich Dad Poor Dad', 'Robert T. Kiyosaki',
'Finance', 499,
'A popular guide to financial education and money management.',
7, '#687d72', 'rich-dad-poor-dad.jpg');