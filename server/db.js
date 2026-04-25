const initSqlJs = require('sql.js');
const fs = require('fs');
const path = require('path');

const DB_PATH = path.join(__dirname, 'freight.db');
let db = null;

async function getDb() {
  if (db) return db;
  const SQL = await initSqlJs();
  if (fs.existsSync(DB_PATH)) {
    const buffer = fs.readFileSync(DB_PATH);
    db = new SQL.Database(buffer);
  } else {
    db = new SQL.Database();
  }
  initTables();
  return db;
}

function saveDb() {
  if (!db) return;
  fs.writeFileSync(DB_PATH, Buffer.from(db.export()));
}

function initTables() {
  db.run('DROP TABLE IF EXISTS freight_logs');
  db.run(`
    CREATE TABLE freight_logs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      trip_date TEXT DEFAULT (date('now','localtime')),
      origin TEXT DEFAULT '',
      destination TEXT DEFAULT '',
      driver TEXT DEFAULT '',
      cargo TEXT DEFAULT '',
      consignor_phone TEXT DEFAULT '',
      weight REAL DEFAULT 0,
      unit_price REAL DEFAULT 0,
      toll REAL DEFAULT 0,
      fuel REAL DEFAULT 0,
      water REAL DEFAULT 0,
      fine REAL DEFAULT 0,
      other_expenses TEXT DEFAULT '[]',
      total_expense REAL DEFAULT 0,
      freight REAL DEFAULT 0,
      net_income REAL DEFAULT 0,
      created_at TEXT DEFAULT (datetime('now','localtime')),
      updated_at TEXT DEFAULT (datetime('now','localtime'))
    )
  `);
  db.run('CREATE INDEX IF NOT EXISTS idx_trip_date ON freight_logs(trip_date)');
  db.run('CREATE INDEX IF NOT EXISTS idx_driver ON freight_logs(driver)');
  saveDb();
}

function runQuery(sql, params = []) {
  const stmt = db.prepare(sql);
  if (sql.trim().toUpperCase().startsWith('SELECT') || sql.trim().toUpperCase().startsWith('WITH')) {
    stmt.bind(params);
    const rows = [];
    while (stmt.step()) rows.push(stmt.getAsObject());
    stmt.free();
    return rows;
  } else {
    const result = stmt.run(params);
    stmt.free();
    saveDb();
    return result;
  }
}

function getRun(sql, params = []) {
  const rows = runQuery(sql, params);
  return rows.length > 0 ? rows[0] : null;
}

function getAllLogs(params = {}) {
  let sql = 'SELECT * FROM freight_logs WHERE 1=1';
  const values = [];
  if (params.date) { sql += ' AND trip_date = ?'; values.push(params.date); }
  if (params.year) { sql += " AND strftime('%Y', trip_date) = ?"; values.push(params.year); }
  if (params.month) { sql += " AND strftime('%Y-%m', trip_date) = ?"; values.push(params.month); }
  if (params.startDate && params.endDate) { sql += ' AND trip_date >= ? AND trip_date <= ?'; values.push(params.startDate, params.endDate); }
  if (params.driver) { sql += ' AND driver LIKE ?'; values.push(`%${params.driver}%`); }
  sql += ' ORDER BY trip_date DESC, id DESC';
  return runQuery(sql, values);
}

function getLogById(id) {
  return getRun('SELECT * FROM freight_logs WHERE id = ?', [id]);
}

const FIELDS = [
  'trip_date','origin','destination','driver','cargo',
  'consignor_phone','weight','unit_price',
  'toll','fuel','water','fine',
  'other_expenses','total_expense','freight','net_income'
];

function parseVal(f, v) {
  if (f === 'other_expenses') {
    if (typeof v === 'string') { try { return JSON.stringify(JSON.parse(v)); } catch { return '[]'; } }
    return JSON.stringify(v || []);
  }
  if (['weight','unit_price','toll','fuel','water','fine','total_expense','freight','net_income'].includes(f)) return parseFloat(v) || 0;
  return v !== undefined && v !== null ? String(v) : '';
}

function createLog(data) {
  const placeholders = FIELDS.map(() => '?').join(', ');
  const values = FIELDS.map(f => parseVal(f, data[f]));
  runQuery(`INSERT INTO freight_logs (${FIELDS.join(',')}) VALUES (${placeholders})`, values);
  return getRun('SELECT * FROM freight_logs ORDER BY id DESC LIMIT 1');
}

function updateLog(id, data) {
  const sets = FIELDS.map(f => `${f} = ?`).concat("updated_at = datetime('now','localtime')");
  const values = FIELDS.map(f => parseVal(f, data[f]));
  runQuery(`UPDATE freight_logs SET ${sets.join(',')} WHERE id = ?`, [...values, id]);
  return getLogById(id);
}

function deleteLog(id) {
  runQuery('DELETE FROM freight_logs WHERE id = ?', [id]);
  return { deleted: true };
}

function getStats(params = {}) {
  let where = '1=1';
  const values = [];
  if (params.year) { where += " AND strftime('%Y', trip_date) = ?"; values.push(params.year); }
  if (params.month) { where += " AND strftime('%Y-%m', trip_date) = ?"; values.push(params.month); }
  if (params.startDate && params.endDate) { where += ' AND trip_date >= ? AND trip_date <= ?'; values.push(params.startDate, params.endDate); }

  const overview = getRun(`
    SELECT COUNT(*) as trips,
      COALESCE(SUM(freight),0) as total_freight,
      COALESCE(SUM(net_income),0) as total_net,
      COALESCE(SUM(total_expense),0) as total_expense,
      COALESCE(AVG(net_income),0) as avg_net,
      COALESCE(SUM(toll),0) as total_toll,
      COALESCE(SUM(fuel),0) as total_fuel,
      COALESCE(SUM(water),0) as total_water,
      COALESCE(SUM(fine),0) as total_fine,
      COUNT(DISTINCT trip_date) as work_days,
      COUNT(DISTINCT driver) as driver_count
    FROM freight_logs WHERE ${where}
  `, values);

  const dailyStats = runQuery(`
    SELECT trip_date, COUNT(*) as trips,
      COALESCE(SUM(freight),0) as freight,
      COALESCE(SUM(total_expense),0) as expense,
      COALESCE(SUM(net_income),0) as net
    FROM freight_logs WHERE ${where}
    GROUP BY trip_date ORDER BY trip_date
  `, values);

  const driverStats = runQuery(`
    SELECT driver, COUNT(*) as trips,
      COALESCE(SUM(freight),0) as freight,
      COALESCE(SUM(net_income),0) as net
    FROM freight_logs WHERE ${where} AND driver != ''
    GROUP BY driver ORDER BY freight DESC LIMIT 10
  `, values);

  return { overview, dailyStats, driverStats };
}

module.exports = { getDb, getAllLogs, getLogById, createLog, updateLog, deleteLog, getStats };
