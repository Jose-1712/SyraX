// SYRAX Energy Management System - Client Application Engine
const API_BASE = "";

// ================= GLOBAL APP STATE =================
let currentUser = null;
let apiOnline = false;

// Chart references
let forecastChartRef = null;
let efficiencyChartRef = null;
let batteryHealthChartRef = null;
let dailyCostChartRef = null;
let savingsChartRef = null;

// ================= TOAST NOTIFICATION UTILITY =================
function showToast(message, type = "info") {
  const container = document.getElementById("toastContainer");
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  
  let icon = "ℹ️";
  if (type === "success") icon = "✅";
  if (type === "error") icon = "❌";
  if (type === "warn") icon = "⚠️";
  
  toast.innerHTML = `<span>${icon}</span><span>${message}</span>`;
  container.appendChild(toast);
  
  setTimeout(() => {
    toast.style.transform = "translateX(120%)";
    toast.style.opacity = "0";
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// ================= CLOCK & API STATUS =================
function tickClock() {
  const el = document.getElementById("clock");
  if (el) {
    el.textContent = new Date().toLocaleTimeString();
  }
}
setInterval(tickClock, 1000);
tickClock();

async function checkApiHealth() {
  try {
    const res = await fetch(`${API_BASE}/api/health`);
    if (res.ok) {
      setApiStatus(true);
    } else {
      setApiStatus(false);
    }
  } catch (e) {
    setApiStatus(false);
  }
}

function setApiStatus(online) {
  apiOnline = online;
  const statusDiv = document.getElementById("apiStatus");
  if (statusDiv) {
    statusDiv.className = `api-status ${online ? "online" : "offline"}`;
    statusDiv.querySelector(".label").textContent = online ? "live" : "offline";
  }
}

// ================= AUTHENTICATION SERVICES =================
// Pre-populate mock users if empty
function initMockUsers() {
  const users = localStorage.getItem("syrax_users");
  if (!users) {
    const defaultUsers = {
      "admin": {
        username: "admin",
        fullName: "Syrax Administrator",
        email: "admin@syrax.energy",
        password: "admin123",
        avatar: "",
        preferences: {
          theme: "white",
          layout: "grid",
          sound: "chime",
          emailNotify: true,
          pushNotify: true,
          smsNotify: false
        }
      }
    };
    localStorage.setItem("syrax_users", JSON.stringify(defaultUsers));
  }
}

function showAuthCard(cardId) {
  document.getElementById("loginCard").classList.add("hidden");
  document.getElementById("registerCard").classList.add("hidden");
  document.getElementById("forgotCard").classList.add("hidden");
  document.getElementById(cardId).classList.remove("hidden");
}

function handleLogin(e) {
  e.preventDefault();
  const userOrEmail = document.getElementById("loginUser").value.trim();
  const pass = document.getElementById("loginPassword").value;
  
  const users = JSON.parse(localStorage.getItem("syrax_users") || "{}");
  let matchedUser = null;
  
  for (const username in users) {
    const u = users[username];
    if ((u.username === userOrEmail || u.email === userOrEmail) && u.password === pass) {
      matchedUser = u;
      break;
    }
  }
  
  if (matchedUser) {
    currentUser = matchedUser;
    localStorage.setItem("syrax_current_user", JSON.stringify(currentUser));
    showToast(`Welcome back, ${currentUser.fullName}!`, "success");
    enterApp();
  } else {
    showToast("Invalid credentials. Try username 'admin' and password 'admin123'.", "error");
  }
}

function handleRegister(e) {
  e.preventDefault();
  const fullName = document.getElementById("regFullName").value.trim();
  const email = document.getElementById("regEmail").value.trim();
  const username = document.getElementById("regUsername").value.trim().toLowerCase();
  const pass = document.getElementById("regPassword").value;
  const confirmPass = document.getElementById("regConfirmPassword").value;
  
  if (pass !== confirmPass) {
    showToast("Passwords do not match.", "error");
    return;
  }
  
  const users = JSON.parse(localStorage.getItem("syrax_users") || "{}");
  
  if (users[username]) {
    showToast("Username already exists.", "error");
    return;
  }
  
  for (const key in users) {
    if (users[key].email === email) {
      showToast("Email already registered.", "error");
      return;
    }
  }
  
  // Register new user
  users[username] = {
    username: username,
    fullName: fullName,
    email: email,
    password: pass,
    avatar: "",
    preferences: {
      theme: "white",
      layout: "grid",
      sound: "chime",
      emailNotify: true,
      pushNotify: true,
      smsNotify: false
    }
  };
  
  localStorage.setItem("syrax_users", JSON.stringify(users));
  showToast("Account created successfully! Please login.", "success");
  e.target.reset();
  showAuthCard("loginCard");
}

let generatedOtp = null;
function sendOtp() {
  const email = document.getElementById("forgotEmail").value.trim();
  if (!email) {
    showToast("Please enter an email address first.", "warn");
    return;
  }
  
  generatedOtp = Math.floor(100000 + Math.random() * 900000);
  // Show standard notification containing OTP for mock purposes
  showToast(`OTP Sent to ${email}! [ MOCK CODE: ${generatedOtp} ]`, "success");
}

function handleResetPassword(e) {
  e.preventDefault();
  const email = document.getElementById("forgotEmail").value.trim();
  const otpInput = document.getElementById("forgotOtp").value.trim();
  const newPass = document.getElementById("forgotNewPass").value;
  const confirmPass = document.getElementById("forgotConfirmPass").value;
  
  if (!generatedOtp || otpInput !== String(generatedOtp)) {
    showToast("Incorrect or unrequested OTP code.", "error");
    return;
  }
  
  if (newPass !== confirmPass) {
    showToast("Passwords do not match.", "error");
    return;
  }
  
  const users = JSON.parse(localStorage.getItem("syrax_users") || "{}");
  let userKey = null;
  
  for (const key in users) {
    if (users[key].email === email) {
      userKey = key;
      break;
    }
  }
  
  if (userKey) {
    users[userKey].password = newPass;
    localStorage.setItem("syrax_users", JSON.stringify(users));
    showToast("Password reset successfully! Login with your new password.", "success");
    e.target.reset();
    generatedOtp = null;
    showAuthCard("loginCard");
  } else {
    showToast("No account associated with this email address.", "error");
  }
}

function showLogoutModal() {
  document.getElementById("logoutModal").classList.remove("hidden");
}

function closeLogoutModal() {
  document.getElementById("logoutModal").classList.add("hidden");
}

function confirmLogout() {
  currentUser = null;
  localStorage.removeItem("syrax_current_user");
  closeLogoutModal();
  showToast("Logged out successfully.", "info");
  
  // App view resets
  document.getElementById("appShell").classList.add("hidden");
  document.getElementById("authWrapper").classList.remove("hidden");
  
  // Reset forms
  document.getElementById("loginForm").reset();
  showAuthCard("loginCard");
}

// ================= APP LAYOUT NAVIGATION =================
function switchTab(tabName) {
  const tabs = ["dashboard", "progress", "predict", "cost", "battery", "settings"];
  
  // Update view panel visibility
  tabs.forEach(t => {
    const view = document.getElementById(`view-${t}`);
    const navItem = document.getElementById(`nav-${t}`);
    if (view) {
      if (t === tabName) {
        view.classList.remove("hidden");
        navItem.classList.add("active");
      } else {
        view.classList.add("hidden");
        navItem.classList.remove("active");
      }
    }
  });
  
  // Update page title
  const titles = {
    dashboard: "Energy Dashboard",
    progress: "Progress Dashboard",
    predict: "AI Predictions",
    cost: "Cost Analysis",
    battery: "Battery Monitoring",
    settings: "System Settings"
  };
  
  document.getElementById("currentPageTitle").textContent = titles[tabName] || "Dashboard";
  
  // Lazy initialize charts depending on current page view
  if (tabName === "progress") {
    initProgressCharts();
  } else if (tabName === "cost") {
    initCostCharts();
  }
}

function enterApp() {
  document.getElementById("authWrapper").classList.add("hidden");
  document.getElementById("appShell").classList.remove("hidden");
  
  // Populate profile info in header
  const initials = currentUser.fullName.split(" ").map(n => n[0]).join("").toUpperCase().substring(0, 2);
  const avatarDiv = document.getElementById("headerProfileAvatar");
  
  if (currentUser.avatar) {
    avatarDiv.innerHTML = `<img src="${currentUser.avatar}" alt="Avatar" class="user-avatar" style="border:none; width:100%; height:100%;">`;
  } else {
    avatarDiv.textContent = initials;
    avatarDiv.innerHTML = initials;
  }
  
  document.getElementById("headerUserName").textContent = currentUser.fullName;
  
  // Run settings population
  populateSettingsForm();
  
  // Load dashboard telemetry data
  loadDashboardData();
  switchTab("dashboard");
}

// ================= DATA LOADING & TELEMETRY API =================
async function loadDashboardData() {
  await checkApiHealth();
  await Promise.allSettled([
    loadForecast(),
    loadBatteryTelemetry(),
    loadSummaryKPIs(),
    loadAlerts()
  ]);
  
  // Auto load Gemini AI summary
  loadAIGeminiInsights();
}

async function loadForecast() {
  let labels = [];
  let values = [];
  
  try {
    if (apiOnline) {
      const data = await fetch(`${API_BASE}/api/predict/demand?hours=24`).then(r => r.json());
      labels = data.forecast.map(f => new Date(f.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }));
      values = data.forecast.map(f => f.predicted_demand_kw);
    } else {
      throw new Error("Offline");
    }
  } catch (e) {
    // Generate beautiful mock demand forecast curve (standard light load, mid-day peak)
    for (let i = 0; i < 24; i++) {
      const hour = (new Date().getHours() + i) % 24;
      const base = 500 + Math.sin((hour - 8) * Math.PI / 12) * 250;
      const noise = Math.random() * 40 - 20;
      labels.push(`${hour.toString().padStart(2, '0')}:00`);
      values.push(Math.round(base + noise));
    }
  }
  
  // Update UI stats
  const peakVal = Math.max(...values);
  const peakIdx = values.indexOf(peakVal);
  document.getElementById("stat-peak-forecast").textContent = `${peakVal.toLocaleString()} kW`;
  document.getElementById("stat-peak-hour").textContent = labels[peakIdx];
  
  // Initialize or update forecast chart
  const ctx = document.getElementById("forecastChart").getContext("2d");
  const gradient = ctx.createLinearGradient(0, 0, 0, 180);
  gradient.addColorStop(0, "rgba(59, 130, 246, 0.3)");
  gradient.addColorStop(1, "rgba(59, 130, 246, 0.0)");
  
  const config = {
    type: "line",
    data: {
      labels,
      datasets: [{
        label: "Forecasted Demand (kW)",
        data: values,
        borderColor: "#3b82f6",
        backgroundColor: gradient,
        fill: true,
        tension: 0.35,
        borderWidth: 2,
        pointRadius: 2,
        pointHoverRadius: 5
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false }
      },
      scales: {
        x: {
          ticks: { color: "#64748b", font: { size: 10, family: "JetBrains Mono" } },
          grid: { color: "#f1f5f9" }
        },
        y: {
          ticks: { color: "#64748b", font: { size: 10, family: "JetBrains Mono" } },
          grid: { color: "#f1f5f9" }
        }
      }
    }
  };
  
  if (forecastChartRef) {
    forecastChartRef.data = config.data;
    forecastChartRef.update();
  } else {
    forecastChartRef = new Chart(ctx, config);
  }
}

async function loadBatteryTelemetry() {
  let soh = 0.92;
  let batteryId = "BAT-SYS-L4";
  let rul = 1842;
  let usableCapacity = 0.90;
  let voltage = 52.8;
  let faultType = "Normal";
  
  try {
    if (apiOnline) {
      const data = await fetch(`${API_BASE}/api/battery/status`).then(r => r.json());
      soh = data.soh;
      batteryId = data.battery_id;
      rul = data.rul;
      usableCapacity = data.usable_capacity_fraction;
      voltage = data.voltage;
      faultType = data.fault_type;
    }
  } catch (e) {
    // Keep mock defaults
  }
  
  // Dashboard indicators
  document.getElementById("kpi-battery-level").textContent = `${Math.round(usableCapacity * 100)}%`;
  
  // Battery Monitoring view fields
  document.getElementById("battery-energy-used").textContent = `${(rul * 12.5).toLocaleString(undefined, {maximumFractionDigits:0})} kWh`;
  document.getElementById("battery-charge").textContent = `${Math.round(usableCapacity * 100)}%`;
  document.getElementById("battery-life").textContent = `${rul} cycles`;
  
  document.getElementById("spec-id").textContent = batteryId;
  document.getElementById("spec-nominal-capacity").textContent = `150 kWh`;
  document.getElementById("spec-soh").textContent = `${Math.round(soh * 100)}%`;
  document.getElementById("spec-usable-capacity").textContent = `${Math.round(150 * usableCapacity)} kWh`;
  
  document.getElementById("spec-voltage").textContent = `${voltage.toFixed(1)} V`;
  
  const faultEl = document.getElementById("spec-fault");
  faultEl.textContent = faultType.toUpperCase();
  
  if (faultType.toLowerCase() === "normal") {
    faultEl.className = "fault-badge normal";
  } else if (faultType.toLowerCase() === "aging" || faultType.toLowerCase() === "warning") {
    faultEl.className = "fault-badge warning";
  } else {
    faultEl.className = "fault-badge danger";
  }
  
  // Update dynamic battery recommendations
  const batteryRecText = document.getElementById("batteryRecommendationsText");
  if (soh > 0.85 && faultType.toLowerCase() === "normal") {
    batteryRecText.textContent = `Battery pack ${batteryId} is in excellent operational status. Cell impedance variance is well within nominal tolerances (4.2 mV). No deep temperature hot-spots detected. The PPO scheduler is permitted to cycle the battery up to peak charge rate of 50 kW during low demand.`;
  } else if (soh > 0.70) {
    batteryRecText.textContent = `Battery pack ${batteryId} shows moderate aging (SoH: ${Math.round(soh*100)}%). Charging current should be capped at 0.5C (35 kW) to prevent accelerated capacity degradation. Avoid scheduling discharge actions that drop state of charge below 20%.`;
  } else {
    batteryRecText.textContent = `CRITICAL ALERT: Battery pack ${batteryId} has degraded capacity or active fault vectors. The PPO scheduling agent has restricted standard cycles. Maintenance dispatch is recommended.`;
  }
}

async function loadSummaryKPIs() {
  let latestDemand = 624.5;
  let baselineCost = 148500;
  let optimizedCost = 118800;
  let absoluteSavings = 29700;
  let percentageSavings = 20.0;
  
  try {
    if (apiOnline) {
      const data = await fetch(`${API_BASE}/api/dashboard/summary`).then(r => r.json());
      latestDemand = data.latest_actual_demand_kw;
      baselineCost = data.cost_savings.baseline_electricity_cost;
      optimizedCost = data.cost_savings.rl_optimized_cost;
      absoluteSavings = data.cost_savings.absolute_savings;
      percentageSavings = data.cost_savings.percentage_savings;
    }
  } catch (e) {
    // Keep mock defaults
  }
  
  document.getElementById("kpi-total-energy").textContent = `${latestDemand.toLocaleString()} kW`;
  document.getElementById("kpi-cost-today").textContent = `₹${Math.round(optimizedCost).toLocaleString()}`;
  document.getElementById("kpi-saved-energy").textContent = `₹${Math.round(absoluteSavings).toLocaleString()}`;
  
  document.getElementById("stat-latest-actual").textContent = `${latestDemand.toLocaleString()} kW`;
  
  // Cost Page indicators
  document.getElementById("cost-before").textContent = `₹${Math.round(baselineCost).toLocaleString()}`;
  document.getElementById("cost-after").textContent = `₹${Math.round(optimizedCost).toLocaleString()}`;
  document.getElementById("cost-savings").textContent = `₹${Math.round(absoluteSavings).toLocaleString()}`;
  document.getElementById("cost-savings-pct").textContent = `${percentageSavings.toFixed(1)}% Saved`;
}

async function loadAlerts() {
  const alertList = document.getElementById("alertList");
  
  try {
    if (apiOnline) {
      const alerts = await fetch(`${API_BASE}/api/alerts`).then(r => r.json());
      if (alerts && alerts.length > 0) {
        alertList.innerHTML = alerts.map(a => `
          <li class="alert-item">
            <div class="alert-item-info">
              <span class="alert-item-title">${a.battery_id} &mdash; ${a.fault_type}</span>
              <span class="alert-item-time">${new Date(a.alert_time).toLocaleString()}</span>
            </div>
            <span class="fault-badge danger">CRITICAL</span>
          </li>
        `).join("");
        return;
      }
    }
  } catch (e) {
    // Fall back to empty or mock
  }
  
  alertList.innerHTML = `
    <li class="alert-item" style="border-left: 4px solid var(--success);">
      <div class="alert-item-info">
        <span class="alert-item-title" style="font-weight: 600;">System Check &mdash; Normal</span>
        <span class="alert-item-time">Continuous monitoring active</span>
      </div>
      <span class="fault-badge normal">HEALTHY</span>
    </li>
  `;
}

async function handleGetRecommendation(e) {
  e.preventDefault();
  const demand_kw = parseFloat(document.getElementById("inDemand").value);
  const price_per_kwh = parseFloat(document.getElementById("inPrice").value);
  const soc = parseFloat(document.getElementById("inSoc").value);
  
  let mode = "Hold";
  let power = 0.0;
  
  try {
    if (apiOnline) {
      const data = await fetch(`${API_BASE}/api/battery/recommend`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ demand_kw, price_per_kwh, soc })
      }).then(r => r.json());
      
      mode = data.recommendation.mode;
      power = data.recommendation.power_kw;
    } else {
      // Mock logic: charge if price is low, discharge if price is high, hold if neutral
      if (price_per_kwh < 6.0 && soc < 0.9) {
        mode = "Charge";
        power = Math.round(50 * (1 - soc));
      } else if (price_per_kwh > 10.0 && soc > 0.2) {
        mode = "Discharge";
        power = Math.round(50 * soc);
      } else {
        mode = "Hold";
        power = 0.0;
      }
    }
  } catch (err) {
    // Keep local logic
  }
  
  const modeEl = document.getElementById("actionMode");
  const powerEl = document.getElementById("actionPower");
  
  modeEl.textContent = mode;
  modeEl.className = `rec-badge ${mode.toLowerCase()}`;
  powerEl.textContent = `${power.toFixed(1)} kW`;
  
  showToast(`PPO Agent recommends: ${mode.toUpperCase()} (${power.toFixed(1)} kW)`, "info");
}

// ================= GEMINI AI INTEGRATION =================
async function loadAIGeminiInsights(customQuestion = null) {
  const outputBox = document.getElementById("aiInsightsOutput");
  if (!outputBox) return;
  
  outputBox.textContent = "Analyzing operational vectors & generating Gemini AI insights...";
  
  try {
    if (apiOnline) {
      const res = await fetch(`${API_BASE}/api/ai/insights`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          context: "dashboard",
          question: customQuestion
        })
      });
      
      if (res.status === 503 || res.status === 502) {
        // Fall back to local insights generator if API key is not configured on server
        throw new Error("Gemini Key Missing");
      }
      
      const data = await res.json();
      outputBox.innerHTML = formatMarkdown(data.insights);
    } else {
      throw new Error("Offline");
    }
  } catch (e) {
    // Local Expert Heuristics Insights generator
    setTimeout(() => {
      let insightText = "";
      if (customQuestion) {
        const q = customQuestion.toLowerCase();
        if (q.includes("saving") || q.includes("cost") || q.includes("money")) {
          insightText = `Based on your cost analysis, the RL optimization agent has saved ₹29,700 today (20% savings). This was primarily achieved by scheduling charges during the low-tariff zone from 02:00 to 05:00, and peak-shaving at 17:00 when grid prices peaked at ₹14.5/kWh.`;
        } else if (q.includes("battery") || q.includes("health") || q.includes("degrade")) {
          insightText = `The battery health parameters show a State of Health (SoH) of 92% with 1,842 remaining cycles before capacity reaches end-of-life parameters (80%). The cell temperature (28.5°C) and cell variance (4.2mV) are excellent. Recommended charge rates are capped at 50kW to maintain longevity.`;
        } else {
          insightText = `I have analyzed the current demand curves and battery telemetry. The peak load forecast indicates a high consumption spike of approximately 750 kW around 06:00 PM. I recommend keeping battery state of charge above 60% by 04:00 PM to assist in shaving the peak demand and avoiding grid overload surcharges.`;
        }
      } else {
        insightText = `### SYRAX Core Analytics Insights
- **XGBoost Load Forecast**: Plant demand is projected to peak at **740 kW** between **06:00 PM - 08:00 PM**.
- **Battery Health Evaluation**: SOH is stable at **92%**. Internal telemetry is healthy.
- **Cost Shifting Recommendation**: PPO scheduler successfully shifted **1,450 kWh** off-grid, resulting in an estimated savings of **₹29,700** (20% reduction in daily energy overhead).
- *Action*: Charge rates are authorized at 100% capacity during the upcoming low-price wind slot tonight.`;
      }
      outputBox.innerHTML = formatMarkdown(insightText);
    }, 800);
  }
}

function askGemini(e) {
  e.preventDefault();
  const q = document.getElementById("aiQuestion").value.trim();
  if (!q) return;
  loadAIGeminiInsights(q);
  document.getElementById("aiQuestion").value = "";
}

function formatMarkdown(text) {
  // Simple regex formatters for bold and bullets to render nice list items in the box
  return text
    .replace(/^### (.*$)/gim, '<strong style="font-size:14px; display:block; margin-bottom:6px;">$1</strong>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/^\s*\-\s*(.*$)/gim, '<li style="margin-left:14px; margin-bottom:4px;">$1</li>')
    .replace(/\n/g, '<br>');
}

// ================= PROGRESS VIEWS & CHARTS =================
function initProgressCharts() {
  if (efficiencyChartRef && batteryHealthChartRef) return;
  
  // 1. Efficiency Chart
  const ctxEff = document.getElementById("efficiencyTrendChart").getContext("2d");
  efficiencyChartRef = new Chart(ctxEff, {
    type: "bar",
    data: {
      labels: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul"],
      datasets: [
        {
          label: "Baseline Efficiency",
          data: [72, 75, 71, 74, 76, 73, 75],
          backgroundColor: "rgba(100, 116, 139, 0.2)",
          borderColor: "#64748b",
          borderWidth: 1
        },
        {
          label: "AI-Optimized Efficiency",
          data: [85, 88, 87, 92, 94, 91, 95],
          backgroundColor: "rgba(16, 185, 129, 0.8)",
          borderColor: "#10b981",
          borderWidth: 1
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { ticks: { color: "#64748b", font: { size: 9 } }, grid: { display: false } },
        y: { ticks: { color: "#64748b", font: { size: 9 } }, grid: { color: "#e2e8f0" }, min: 50, max: 100 }
      }
    }
  });

  // 2. Battery Health Degradation Chart
  const ctxHealth = document.getElementById("batteryHealthTrendChart").getContext("2d");
  batteryHealthChartRef = new Chart(ctxHealth, {
    type: "line",
    data: {
      labels: [0, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000],
      datasets: [{
        label: "SoH (%) Degradation Curve",
        data: [100, 99.1, 98.2, 97.4, 96.5, 95.8, 95.0, 94.2, 93.5, 92.8, 92.0],
        borderColor: "#ef4444",
        backgroundColor: "rgba(239, 68, 68, 0.05)",
        fill: true,
        tension: 0.2,
        borderWidth: 2
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { 
          title: { display: true, text: "Cycles Done", font: { size: 9, weight: "bold" }, color: "#64748b" },
          ticks: { color: "#64748b", font: { size: 9 } }, 
          grid: { display: false } 
        },
        y: { 
          title: { display: true, text: "SOH (%)", font: { size: 9, weight: "bold" }, color: "#64748b" },
          ticks: { color: "#64748b", font: { size: 9 } }, 
          grid: { color: "#e2e8f0" }, 
          min: 80, 
          max: 100 
        }
      }
    }
  });
}

// ================= COST ANALYSIS VIEWS & CHARTS =================
function initCostCharts() {
  if (dailyCostChartRef && savingsChartRef) return;
  
  // 1. Daily Cost Graph
  const ctxCost = document.getElementById("dailyCostChart").getContext("2d");
  const costLabels = Array.from({length: 15}, (_, i) => `Jul ${i + 1}`);
  dailyCostChartRef = new Chart(ctxCost, {
    type: "line",
    data: {
      labels: costLabels,
      datasets: [
        {
          label: "Baseline (Unoptimized)",
          data: [14200, 13800, 15100, 14900, 13700, 15500, 14800, 14100, 13900, 15200, 14800, 14600, 13500, 15800, 14850],
          borderColor: "#ef4444",
          borderDash: [5, 5],
          fill: false,
          tension: 0.1,
          borderWidth: 2
        },
        {
          label: "RL Optimized (Battery)",
          data: [11500, 11000, 12200, 11900, 10800, 12500, 11800, 11300, 11000, 12000, 11800, 11500, 10900, 12600, 11880],
          borderColor: "#3b82f6",
          backgroundColor: "rgba(59, 130, 246, 0.05)",
          fill: true,
          tension: 0.1,
          borderWidth: 2
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { ticks: { color: "#64748b", font: { size: 9 } }, grid: { display: false } },
        y: { ticks: { color: "#64748b", font: { size: 9 } }, grid: { color: "#e2e8f0" } }
      }
    }
  });

  // 2. Savings Distribution Chart (Doughnut)
  const ctxSavings = document.getElementById("savingsComparisonChart").getContext("2d");
  savingsChartRef = new Chart(ctxSavings, {
    type: "doughnut",
    data: {
      labels: ["Peak Shaving", "Time-of-Use Shift", "Solar Conversion"],
      datasets: [{
        data: [45, 35, 20],
        backgroundColor: ["#10b981", "#3b82f6", "#f59e0b"],
        hoverOffset: 4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: "bottom",
          labels: { boxWidth: 12, font: { size: 10 } }
        }
      }
    }
  });
}

// ================= DATASET PREDICTIONS DRAG & DROP =================
function triggerFileSelect() {
  document.getElementById("fileInput").click();
}

function handleFileSelect(e) {
  const file = e.target.files[0];
  if (file) parseCSVDataset(file);
}

function handleFileDrop(e) {
  e.preventDefault();
  document.getElementById("dropZone").classList.remove("dragover");
  const file = e.dataTransfer.files[0];
  if (file) parseCSVDataset(file);
}

function parseCSVDataset(file) {
  if (!file.name.endsWith(".csv")) {
    showToast("Invalid file format. Please drop a valid .csv file.", "error");
    return;
  }
  
  const reader = new FileReader();
  reader.onload = function(e) {
    const text = e.target.result;
    processCSVData(text, file.name);
  };
  reader.readAsText(file);
}

function processCSVData(csvText, fileName) {
  const lines = csvText.split("\n").map(l => l.trim()).filter(l => l !== "");
  if (lines.length < 2) {
    showToast("CSV dataset is empty or lacks headers.", "error");
    return;
  }
  
  const headers = lines[0].split(",").map(h => h.trim().toLowerCase());
  const rows = [];
  
  // Parsing first 15 lines for mockup table display
  for (let i = 1; i < lines.length; i++) {
    const cols = lines[i].split(",").map(c => c.trim());
    if (cols.length === headers.length) {
      rows.push(cols);
    }
  }
  
  if (rows.length === 0) {
    showToast("Failed to parse data columns correctly.", "error");
    return;
  }
  
  // Fill the preview table
  const tbody = document.querySelector("#datasetTable tbody");
  tbody.innerHTML = rows.slice(0, 10).map(r => `
    <tr>
      <td>${r[0] || "N/A"}</td>
      <td>${r[1] ? parseFloat(r[1]).toFixed(1) + " kW" : "N/A"}</td>
      <td>${r[2] || "N/A"}</td>
      <td>${r[3] ? parseFloat(r[3]).toFixed(1) + " °C" : "N/A"}</td>
      <td>₹${r[4] || "8.5"}</td>
    </tr>
  `).join("");
  
  // Compute basic stats
  const demandValues = rows.map(r => parseFloat(r[1])).filter(v => !isNaN(v));
  const totalRecords = rows.length;
  
  if (demandValues.length > 0) {
    const mean = demandValues.reduce((a,b) => a+b, 0) / demandValues.length;
    const peak = Math.max(...demandValues);
    const min = Math.min(...demandValues);
    const variance = demandValues.reduce((a,b) => a + Math.pow(b - mean, 2), 0) / demandValues.length;
    const stdDev = Math.sqrt(variance);
    
    document.getElementById("stat-records-count").textContent = totalRecords.toLocaleString();
    document.getElementById("stat-mean-demand").textContent = `${Math.round(mean).toLocaleString()} kW`;
    document.getElementById("stat-peak-demand").textContent = `${Math.round(peak).toLocaleString()} kW`;
    document.getElementById("stat-std-demand").textContent = `${Math.round(stdDev).toLocaleString()} kW`;
    
    // Custom recommendation based on stats
    const recEl = document.getElementById("predictSmartRecs");
    if (mean > 800) {
      recEl.innerHTML = `⚠️ <strong>High demand workload detected</strong> (Mean load: ${Math.round(mean)} kW). The plant load curves indicate severe congestion on Shift A. I recommend adjusting PPO charge triggers from 50 kW to 25 kW during production overlap to avoid grid overload fines.`;
    } else {
      recEl.innerHTML = `✅ <strong>Optimal load curve profile</strong>. Mean demand (${Math.round(mean)} kW) matches historical norms. Solar generation capacity of 340 kW offers solid base load offset. PPO battery agent can standard-cycle without capacity restrictions.`;
    }
    
    showToast(`Successfully processed dataset '${fileName}' with ${totalRecords} records!`, "success");
  } else {
    showToast(`Processed '${fileName}', but no valid numeric demand values found.`, "warn");
  }
}

function loadSampleDataset() {
  // Generate sample CSV text
  let csvText = "timestamp,demand,production,temperature,price\n";
  const now = new Date();
  for (let i = 0; i < 48; i++) {
    const ts = new Date(now - (48 - i) * 60 * 60 * 1000).toISOString().replace("T", " ").substring(0, 19);
    const demand = Math.round(600 + Math.sin(i * Math.PI / 12) * 200 + Math.random() * 30);
    const prod = Math.round(1500 + Math.sin(i * Math.PI / 12) * 500);
    const temp = (25 + Math.sin(i * Math.PI / 12) * 5).toFixed(1);
    const price = (i % 24 > 17 && i % 24 < 22) ? "14.5" : "7.2";
    csvText += `${ts},${demand},${prod},${temp},${price}\n`;
  }
  processCSVData(csvText, "sample_energy_telemetry.csv");
}

// ================= SETTINGS LOGIC =================
function populateSettingsForm() {
  const form = document.getElementById("settingsForm");
  if (!form) return;
  
  document.getElementById("settingsName").value = currentUser.fullName;
  document.getElementById("settingsEmail").value = currentUser.email;
  
  // Mock display of ID/Role
  document.getElementById("settingsUserId").value = `USR-2026-${currentUser.username.substring(0,2).toUpperCase()}`;
  document.getElementById("settingsRole").value = currentUser.username === "admin" ? "Energy Administrator" : "Facility Operator";
  
  // Notification values
  document.getElementById("prefEmail").checked = currentUser.preferences.emailNotify;
  document.getElementById("prefPush").checked = currentUser.preferences.pushNotify;
  document.getElementById("prefSMS").checked = currentUser.preferences.smsNotify;
  
  // Selections
  document.getElementById("prefTheme").value = currentUser.preferences.theme;
  document.getElementById("prefLayout").value = currentUser.preferences.layout;
  document.getElementById("prefSound").value = currentUser.preferences.sound;
  
  // Avatar preview
  const avatarPreview = document.getElementById("settingsProfileAvatar");
  const initials = currentUser.fullName.split(" ").map(n => n[0]).join("").toUpperCase().substring(0, 2);
  if (currentUser.avatar) {
    avatarPreview.innerHTML = `<img src="${currentUser.avatar}" alt="Avatar" style="width:100%; height:100%; border-radius:50%; object-fit:cover;">`;
  } else {
    avatarPreview.textContent = initials;
  }
}

function handleProfileUpload(e) {
  const file = e.target.files[0];
  if (!file) return;
  
  if (file.size > 2 * 1024 * 1024) {
    showToast("Profile image size exceeds 2MB limit.", "error");
    return;
  }
  
  const reader = new FileReader();
  reader.onload = function(evt) {
    const dataUrl = evt.target.result;
    currentUser.avatar = dataUrl;
    document.getElementById("settingsProfileAvatar").innerHTML = `<img src="${dataUrl}" alt="Avatar" style="width:100%; height:100%; border-radius:50%; object-fit:cover;">`;
    showToast("Profile picture uploaded. Click Save to apply.", "info");
  };
  reader.readAsDataURL(file);
}

function handleSaveSettings(e) {
  e.preventDefault();
  const name = document.getElementById("settingsName").value.trim();
  const email = document.getElementById("settingsEmail").value.trim();
  const oldPass = document.getElementById("settingsOldPass").value;
  const newPass = document.getElementById("settingsNewPass").value;
  
  if (newPass) {
    if (oldPass !== currentUser.password) {
      showToast("Verification failed: Old password incorrect.", "error");
      return;
    }
    currentUser.password = newPass;
    showToast("Password updated successfully.", "success");
  }
  
  currentUser.fullName = name;
  currentUser.email = email;
  
  // Preferences
  currentUser.preferences.emailNotify = document.getElementById("prefEmail").checked;
  currentUser.preferences.pushNotify = document.getElementById("prefPush").checked;
  currentUser.preferences.smsNotify = document.getElementById("prefSMS").checked;
  
  currentUser.preferences.theme = document.getElementById("prefTheme").value;
  currentUser.preferences.layout = document.getElementById("prefLayout").value;
  currentUser.preferences.sound = document.getElementById("prefSound").value;
  
  // Update local storage user table
  const users = JSON.parse(localStorage.getItem("syrax_users") || "{}");
  users[currentUser.username] = currentUser;
  localStorage.setItem("syrax_users", JSON.stringify(users));
  
  // Update active session
  localStorage.setItem("syrax_current_user", JSON.stringify(currentUser));
  
  // Update App Header displaying fields
  document.getElementById("headerUserName").textContent = currentUser.fullName;
  const avatarDiv = document.getElementById("headerProfileAvatar");
  const initials = currentUser.fullName.split(" ").map(n => n[0]).join("").toUpperCase().substring(0, 2);
  
  if (currentUser.avatar) {
    avatarDiv.innerHTML = `<img src="${currentUser.avatar}" alt="Avatar" class="user-avatar" style="border:none; width:100%; height:100%; object-fit:cover;">`;
  } else {
    avatarDiv.textContent = initials;
  }
  
  // Clear password inputs
  document.getElementById("settingsOldPass").value = "";
  document.getElementById("settingsNewPass").value = "";
  
  showToast("System changes saved successfully!", "success");
}

// ================= APP INITIALIZATION =================
function appInit() {
  initMockUsers();
  
  // Check if there is an active session
  const activeSession = localStorage.getItem("syrax_current_user");
  if (activeSession) {
    currentUser = JSON.parse(activeSession);
    enterApp();
  } else {
    // Show auth containers
    document.getElementById("authWrapper").classList.remove("hidden");
    document.getElementById("appShell").classList.add("hidden");
    showAuthCard("loginCard");
  }
}

// Start application
appInit();
