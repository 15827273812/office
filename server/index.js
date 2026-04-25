const express = require('express');
const cors = require('cors');
const path = require('path');
const { getDb, getAllLogs, getLogById, createLog, updateLog, deleteLog, getStats } = require('./db');

const app = express();
const PORT = process.env.PORT || 3456;

app.use(cors());
app.use(express.json({ limit: '10mb' }));
app.use(express.static(path.join(__dirname, '..', 'public')));

function safeParseJSON(str, fallback) {
  try { return JSON.parse(str); } catch { return fallback; }
}

app.get('/api/logs', (req, res) => {
  try {
    const { date, year, month, startDate, endDate, driver } = req.query;
    const logs = getAllLogs({ date, year, month, startDate, endDate, driver });
    const parsed = logs.map(log => ({ ...log, other_expenses: safeParseJSON(log.other_expenses, []) }));
    res.json({ success: true, data: parsed });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

app.get('/api/logs/:id', (req, res) => {
  try {
    const log = getLogById(parseInt(req.params.id));
    if (!log) return res.status(404).json({ success: false, error: '记录不存在' });
    log.other_expenses = safeParseJSON(log.other_expenses, []);
    res.json({ success: true, data: log });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

app.post('/api/logs', (req, res) => {
  try {
    const log = createLog(req.body);
    log.other_expenses = safeParseJSON(log.other_expenses, []);
    res.json({ success: true, data: log });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

app.put('/api/logs/:id', (req, res) => {
  try {
    const log = updateLog(parseInt(req.params.id), req.body);
    if (!log) return res.status(404).json({ success: false, error: '记录不存在' });
    log.other_expenses = safeParseJSON(log.other_expenses, []);
    res.json({ success: true, data: log });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

app.delete('/api/logs/:id', (req, res) => {
  try {
    deleteLog(parseInt(req.params.id));
    res.json({ success: true, data: { deleted: true } });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

app.get('/api/stats', (req, res) => {
  try {
    const { year, month, startDate, endDate } = req.query;
    const stats = getStats({ year, month, startDate, endDate });
    res.json({ success: true, data: stats });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, '..', 'public', 'index.html'));
});

async function start() {
  await getDb();
  app.listen(PORT, '0.0.0.0', () => {
    console.log(`✅ 货运物流 App 已启动`);
    console.log(`   🌐 本地: http://localhost:${PORT}`);
    console.log(`   📱 手机访问: http://<服务器IP>:${PORT}`);
  });
}

start().catch(err => {
  console.error('启动失败:', err);
  process.exit(1);
});
