# 🎓 IU Marketplace System

A modern student marketplace web application that allows users to **buy, sell, or gift items** within a university community.
Built with a **premium UI design**, real-time interactions, and **Arabic (RTL) support**.

---

## 🚀 Features

### 👤 User Features

* Secure user registration and login
* Create listings (Sell or Gift items)
* Upload item images
* View item details (restricted for guests)
* Contact sellers via WhatsApp
* Comment on listings
* Rate sellers with ⭐ star ratings
* Manage personal listings (edit, renew, delete)

---

### 🛍️ Marketplace Features

* Browse listings with search and filtering
* Buy vs Gift badge indicators
* Only active listings are displayed
* Weekly listing renewal system

---

### 🛡️ Admin Features

* Manage users (block, hide, delete)
* Moderate listings (hide/delete)
* Moderate comments
* Admin dashboard with statistics

---

### 🎨 UI/UX Features

* Premium modern UI design
* Responsive layout (mobile + desktop)
* Icon-based navigation (Font Awesome)
* Smooth animations and hover effects
* Clean product detail page layout

---

### 🌍 Arabic Language Support

* Full Arabic translation support
* RTL (Right-to-Left) layout handling
* Language toggle (EN / AR)
* Arabic typography integration

---

## 🛠️ Tech Stack

| Layer         | Technology                |
| ------------- | ------------------------- |
| Backend       | Flask (Python)            |
| Frontend      | HTML, CSS, Jinja2         |
| Database      | MySQL                     |
| ORM           | SQLAlchemy                |
| UI Styling    | Custom CSS + Font Awesome |
| Deployment    | Vercel                    |
| Image Storage | Static / Uploads          |

---

## 📂 Project Structure

```
iu-marketplace/
│
├── app.py
├── models.py
├── requirements.txt
│
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── listing_detail.html
│   ├── create_listing.html
│   ├── edit_listing.html
│   ├── login.html
│   ├── register.html
│   ├── my_listings.html
│   └── admin_dashboard.html
│
├── static/
│   ├── css/
│   │   └── style.css
│   ├── images/
│   └── uploads/
│
└── README.md
```

---

## ⚙️ Installation & Setup

### 1. Clone Repository

```bash
git clone https://github.com/your-username/iu-marketplace.git
cd iu-marketplace
```

### 2. Create Virtual Environment

```bash
python -m venv venv
venv\Scripts\activate   # Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create `.env` or set variables:

```text
DATABASE_URL=your_database_url
SECRET_KEY=your_secret_key
```

### 5. Run the Application

```bash
python app.py
```

---

## 🌐 Deployment

This project is deployed using **Vercel**.

### Steps:

1. Push project to GitHub
2. Import project into Vercel
3. Add environment variables
4. Deploy

---

## 🔀 Git Workflow

```bash
# Create feature branch
git checkout -b feature/new-feature

# Commit changes
git add .
git commit -m "Add new feature"

# Push branch
git push -u origin feature/new-feature

# Merge into main
git checkout main
git merge feature/new-feature
git push
```

---



## 📈 Future Improvements

* Real-time chat system
* Recommendation system (similar listings)
* Payment integration
* Push notifications
* Advanced search filters

---

## 👨‍💻 Author

**Abdul Basit**
Computer Science Student
Specializing in Cybersecurity

---

## 📜 License

This project is for educational purposes.
