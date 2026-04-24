# 🔥 AGNI RAKSHAK

### IoT-Based Forest Fire Detection System

AGNI RAKSHAK is an end-to-end **IoT + Machine Learning system** designed to detect and predict forest fire risks in real-time using distributed sensor networks and intelligent data processing.

---

## 🚀 Overview

This project simulates a **smart forest ecosystem** where multiple IoT sensor nodes monitor environmental conditions and transmit data through a mesh network to a central system.

The backend processes this data using a **Machine Learning model (Random Forest)** to predict fire risk, and results are visualized on a **real-time web dashboard**.

---

## 🏗️ Project Structure

```
AGNI-RAKSHAK/
│
├── backend/        # FastAPI server + ML model + TCP listener
├── contiki/        # Sensor & Sink node code (C, Contiki-NG)
├── frontend/       # Dashboard (HTML, CSS, JS)
│
└── README.md
```

---

## ⚙️ Tech Stack

### 🌐 IoT & Simulation

* Contiki-NG
* Cooja Simulator
* C Programming

### 🧠 Machine Learning

* Scikit-learn (Random Forest)
* Joblib

### 🔧 Backend

* Python
* FastAPI
* TCP Socket Programming

### 🎨 Frontend

* HTML, CSS, JavaScript
* WebSockets
* Chart.js

---

## 🔄 System Architecture

```
Sensor Nodes → Sink Node → Serial Socket → TCP Server → Parser → ML Model → WebSocket → Dashboard
```

---

## 🌊 Data Flow

1. Sensor nodes generate environmental data (temperature, humidity, wind, moisture)
2. Data is transmitted via **RPL IPv6 Mesh Network**
3. Sink node collects and prints JSON data
4. Cooja Serial Socket sends data to backend via TCP
5. Python backend parses incoming data
6. ML model predicts fire risk
7. Results are broadcast via WebSocket
8. Dashboard updates in real-time

---

## 📊 Features

* 🌲 Real-time Environmental Monitoring
* 🌐 Mesh Networking (RPL Protocol)
* 🤖 AI-based Fire Risk Prediction
* 📡 Live Data Streaming
* 📊 Interactive Dashboard
* 🔥 Instant Fire Alerts (SAFE / WARNING / FIRE)

---

## ▶️ How to Run

### 1️⃣ Run Cooja Simulation

* Load `sensor.c` and `sink.c`
* Enable Serial Socket Plugin
* Set TCP Port → `5678`

---

### 2️⃣ Start Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app:app --reload
```

---

### 3️⃣ Run Frontend

* Open `frontend/index.html`
  **OR** use Live Server in VS Code

---

## 📈 Output

* Real-time sensor data visualization
* Fire risk prediction:

  * ✅ SAFE
  * ⚠️ WARNING
  * 🔥 FIRE

---

## ⚠️ Challenges

* Sensor Accuracy Limitations
* Network Reliability (RPL Constraints)
* ML False Positives
* Power Constraints in IoT Nodes

---

## 🔮 Future Scope

* Integration with Satellite Data
* Deep Learning Models (CNN / LSTM)
* Mobile App for Alerts
* Drone-based Monitoring
* Real-world Deployment

---

## 👨‍💻 Author

**Saumya Srivastava**
B.Tech IT | IoT + AI/ML Developer

---

## ⭐ Support

If you found this project useful:

* ⭐ Star this repository
* 🍴 Fork and improve
* 📢 Share with others

---

## 📌 License

This project is for **educational and research purposes**.
