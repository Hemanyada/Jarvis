# Jarvis 🤖📱

AI-powered smartphone price comparison and recommendation assistant for the Indian market.

Jarvis helps you find the **best smartphone deals**, compare **specifications**, and get **AI-powered buying advice** — all in one place.

---

## ✨ Features

* 🔎 Search smartphone prices across Indian stores (Amazon, Flipkart, Croma, brand stores)
* 📊 Compare prices with visual charts
* 🧠 AI assistant for phone recommendations
* ⚙️ Automatic spec extraction (display, processor, camera, battery)
* 🏷️ Smart phone tagging (Camera Focused / Performance / All-rounder)
* 💬 Chat interface for interactive queries
* 📈 Best deal detection

---

## 🛠️ Tech Stack

* **Frontend:** Streamlit
* **AI Model:** Google Gemini
* **Search API:** Exa
* **Language:** Python
* **Libraries:** pandas, requests, python-dotenv

---

## 🚀 Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/jarvis.git
cd jarvis
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

or (if using uv)

```bash
uv sync
```

### 3. Set environment variables

Create a `.env` file in the root directory:

```
EXA_API_KEY=your_exa_api_key
GEMINI_API_KEY=your_gemini_api_key
```

---

### 4. Run the app

```bash
streamlit run app.py
```

---

## 💡 Example Queries

* Best phone under ₹30,000
* Best camera phone
* iPhone 15 price in India
* Compare Pixel 8, S23, iPhone 14
* Is this a good deal?

---

## 📸 Features Overview

* Price comparison across platforms
* AI-powered phone recommendations
* Spec comparison table
* Interactive chat assistant
* Best deal detection

---

## 📂 Project Structure

```
jarvis/
│
├── app.py          # Streamlit UI
├── ai.py           # AI assistant logic
├── utils.py        # Price search + spec extraction
├── main.py         # Entry point
├── pyproject.toml  # Project config
└── README.md
```

---

## 🎯 Use Cases

* Compare phone prices instantly
* Find best deals online
* Get AI buying recommendations
* Compare specs before purchasing
* Research smartphones quickly

---

## 🔮 Future Improvements

* Add more stores
* Price history tracking
* User wishlist
* Notification for price drops
* Mobile responsive UI

---

## 🤝 Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss.

---
