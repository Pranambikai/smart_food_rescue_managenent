-- Create Database if not exists
CREATE DATABASE IF NOT EXISTS smart_food_rescue_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE smart_food_rescue_db;

-- 1. Donors Table
CREATE TABLE IF NOT EXISTS donors (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    phone VARCHAR(15) NOT NULL,
    password VARCHAR(255) NOT NULL,
    address VARCHAR(255) NOT NULL,
    lat DECIMAL(10, 8) DEFAULT 10.3673,
    lng DECIMAL(11, 8) DEFAULT 77.9803,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 2. Trusts Table (Admin-Managed)
CREATE TABLE IF NOT EXISTS trusts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    phone VARCHAR(15) NOT NULL,
    password VARCHAR(255) NOT NULL,
    location VARCHAR(255) NOT NULL,
    lat DECIMAL(10, 8) DEFAULT 10.3685,
    lng DECIMAL(11, 8) DEFAULT 77.9754,
    accepted_categories TEXT DEFAULT 'Veg Meals,Non-Veg,Bakery,Fruits,Rice/Sambar',
    required_kg DECIMAL(10, 2) DEFAULT 50.00,
    availability_status VARCHAR(50) DEFAULT 'Active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 3. Volunteers Table
CREATE TABLE IF NOT EXISTS volunteers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    phone VARCHAR(15) NOT NULL,
    password VARCHAR(255) NOT NULL,
    current_lat DECIMAL(10, 8) DEFAULT 10.3750,
    current_lng DECIMAL(11, 8) DEFAULT 77.9700,
    status VARCHAR(50) DEFAULT 'Available',
    task_status VARCHAR(100) DEFAULT 'Available',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 4. Recycling Centers Table (Admin-Managed)
CREATE TABLE IF NOT EXISTS recycling_centers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    center_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    location VARCHAR(255) NOT NULL,
    lat DECIMAL(10, 8) DEFAULT 10.3700,
    lng DECIMAL(11, 8) DEFAULT 77.9900,
    accepted_categories TEXT DEFAULT 'Organic Waste,Cooked Food,Fruits,Vegetables',
    supported_qty DECIMAL(10, 2) DEFAULT 500.00,
    available_capacity DECIMAL(10, 2) DEFAULT 500.00,
    availability_status VARCHAR(50) DEFAULT 'Active',
    contact_phone VARCHAR(15) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 5. Buyers Table
CREATE TABLE IF NOT EXISTS buyers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    phone VARCHAR(15) NOT NULL,
    password VARCHAR(255) NOT NULL,
    address VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 6. Admins Table
CREATE TABLE IF NOT EXISTS admins (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL
) ENGINE=InnoDB;

-- 7. Donations Table
CREATE TABLE IF NOT EXISTS donations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    donor_id INT,
    food_type VARCHAR(255) NOT NULL,
    quantity_kg DECIMAL(10, 2) NOT NULL,
    location VARCHAR(255) NOT NULL,
    food_condition VARCHAR(50) DEFAULT 'Fresh',
    storage_condition VARCHAR(100) DEFAULT 'Room Temperature',
    expiry_time TIMESTAMP NULL,
    status VARCHAR(150) DEFAULT 'Pending Matching',
    accepted_trust_id INT,
    volunteer_id INT,
    volunteer_status VARCHAR(50) DEFAULT 'None',
    volunteer_needed INT DEFAULT 0,
    recycling_center_id INT,
    recycling_status VARCHAR(150) DEFAULT 'Pending',
    delivery_otp VARCHAR(10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (donor_id) REFERENCES donors(id) ON DELETE CASCADE,
    FOREIGN KEY (accepted_trust_id) REFERENCES trusts(id) ON DELETE SET NULL,
    FOREIGN KEY (volunteer_id) REFERENCES volunteers(id) ON DELETE SET NULL,
    FOREIGN KEY (recycling_center_id) REFERENCES recycling_centers(id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- 8. Trust Notifications Tracking Table
CREATE TABLE IF NOT EXISTS trust_notifications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    donation_id INT NOT NULL,
    trust_id INT NOT NULL,
    distance_km DECIMAL(6, 2) NOT NULL,
    response_status VARCHAR(50) DEFAULT 'Pending', -- Pending, Accepted, Rejected, Closed
    notified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    responded_at TIMESTAMP NULL,
    FOREIGN KEY (donation_id) REFERENCES donations(id) ON DELETE CASCADE,
    FOREIGN KEY (trust_id) REFERENCES trusts(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 9. Recycling Notifications Tracking Table
CREATE TABLE IF NOT EXISTS recycling_notifications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    donation_id INT NOT NULL,
    recycling_center_id INT NOT NULL,
    distance_km DECIMAL(6, 2) NOT NULL,
    response_status VARCHAR(50) DEFAULT 'Pending', -- Pending, Accepted, Rejected, Closed
    notified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    responded_at TIMESTAMP NULL,
    FOREIGN KEY (donation_id) REFERENCES donations(id) ON DELETE CASCADE,
    FOREIGN KEY (recycling_center_id) REFERENCES recycling_centers(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 10. Products Table (Green Marketplace)
CREATE TABLE IF NOT EXISTS products (
    id INT AUTO_INCREMENT PRIMARY KEY,
    recycler_id INT,
    product_name VARCHAR(255) NOT NULL,
    description TEXT,
    price DECIMAL(10, 2) NOT NULL,
    quantity INT NOT NULL,
    image_url VARCHAR(255) DEFAULT '/static/images/compost.jpg',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (recycler_id) REFERENCES recycling_centers(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 11. Marketplace Orders Table
CREATE TABLE IF NOT EXISTS marketplace_orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    buyer_id INT,
    product_id INT,
    recycler_id INT,
    order_qty INT NOT NULL,
    total_price DECIMAL(10, 2) NOT NULL,
    delivery_address VARCHAR(255) NOT NULL,
    buyer_phone VARCHAR(15) NOT NULL,
    status VARCHAR(100) DEFAULT 'Order Placed (Awaiting Plant Dispatch)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (buyer_id) REFERENCES buyers(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
    FOREIGN KEY (recycler_id) REFERENCES recycling_centers(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 12. Notifications Table
CREATE TABLE IF NOT EXISTS notifications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    recipient_type VARCHAR(50) NOT NULL,
    recipient_id INT DEFAULT 1,
    message TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- Default Seed Data
INSERT INTO admins (username, password) VALUES ('admin', 'admin123')
ON DUPLICATE KEY UPDATE username=username;

INSERT INTO trusts (id, name, email, phone, password, location, lat, lng, accepted_categories, required_kg, availability_status)
VALUES 
(1, 'Gandhigram Rural Welfare Trust', 'trust@sfr.com', '9876543210', 'password123', 'Gandhigram Post, Dindigul', 10.3685, 77.9754, 'Veg Meals,Rice/Sambar', 20.00, 'Active'),
(2, 'Annai Charity Home', 'annai@sfr.com', '9876543212', 'password123', 'Round Road, Dindigul', 10.3690, 77.9760, 'Veg Meals,Bakery,Fruits', 15.00, 'Active')
ON DUPLICATE KEY UPDATE name=name;

INSERT INTO recycling_centers (id, center_name, email, password, location, lat, lng, accepted_categories, supported_qty, available_capacity, availability_status, contact_phone)
VALUES (1, 'Nilaiyur Bio-Conversion Centre', 'recycler@sfr.com', 'password123', 'Nilaiyur Road, Dindigul', 10.3700, 77.9900, 'Organic Waste,Cooked Food,Fruits,Vegetables', 500.00, 500.00, 'Active', '9876543210')
ON DUPLICATE KEY UPDATE center_name=center_name;

INSERT INTO volunteers (id, name, phone, password, current_lat, current_lng, status, task_status)
VALUES (1, 'Karthik', '9876543211', 'password123', 10.3750, 77.9700, 'Available', 'Available')
ON DUPLICATE KEY UPDATE name=name;

INSERT INTO products (id, recycler_id, product_name, description, price, quantity)
VALUES (1, 1, 'Organic Bio-Compost (Meals Derived)', 'High nitrogen organic fertilizer for horticulture, vegetables, and lawns.', 220.00, 50)
ON DUPLICATE KEY UPDATE product_name=product_name;