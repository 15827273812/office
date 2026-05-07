const initSqlJs = require('sql.js');
const fs = require('fs');
const path = require('path');

const DB_PATH = path.join(__dirname, 'freight.db');
const SQL_FILE = path.join(__dirname, 'sql-queries.json');

// Load all SQL queries from external JSON file
const sql = JSON.parse(fs.readFileSync(SQL_FILE, 'utf8'));
const FIELDS = sql.fields.log_fields;
const NUMERIC_FIELDS = new Set(sql.fields.numeric_fields);

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
  db.run(sql.schema.drop_freight_logs);
  db.run(sql.schema.create_freight_logs);
  db.run(sql.schema.index_trip_date);
  db.run(sql.schema.index_driver);
  saveDb();
}

function runQuery(query, params = []) {
  const stmt = db.prepare(query);
  if (query.trim().toUpperCase().startsWith('SELECT') || query.trim().toUpperCase().startsWith('WITH')) {
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

function getRun(query, params = []) {
  const rows = runQuery(query, params);
  return rows.length > 0 ? rows[0] : null;
}

function buildWhere(params) {
  const clauses = [];
  const values = [];
  if (params.date)      { clauses.push(sql.queries.where_trip_date_eq);      values.push(params.date); }
  if (params.year)      { clauses.push(sql.queries.where_year_eq);           values.push(params.year); }
  if (params.month)     { clauses.push(sql.queries.where_year_month_eq);     values.push(params.month); }
  if (params.startDate && params.endDate) { clauses.push(sql.queries.where_date_range); values.push(params.startDate, params.endDate); }
  if (params.driver)    { clauses.push(sql.queries.where_driver_like);       values.push(`%${params.driver}%`); }
  return { where: clauses.join(' AND ') || sql.queries.where_1_eq_1, values };
}

function getAllLogs(params = {}) {
  const { where, values } = buildWhere(params);
  const query = [sql.queries.select_all_logs_base, 'AND', where, sql.queries.order_desc].join(' ');
  return runQuery(query, values);
}

function getLogById(id) {
  return getRun(sql.queries.select_log_by_id, [id]);
}

function parseVal(f, v) {
  if (f === 'other_expenses') {
    if (typeof v === 'string') { try { return JSON.stringify(JSON.parse(v)); } catch { return '[]'; } }
    return JSON.stringify(v || []);
  }
  if (NUMERIC_FIELDS.has(f)) return parseFloat(v) || 0;
  return v !== undefined && v !== null ? String(v) : '';
}

function createLog(data) {
  const placeholders = FIELDS.map(() => '?').join(', ');
  const values = FIELDS.map(f => parseVal(f, data[f]));
  runQuery(sql.queries.insert_log, values);
  return getRun(sql.queries.select_last_log);
}

function updateLog(id, data) {
  const values = FIELDS.map(f => parseVal(f, data[f]));
  runQuery(sql.queries.update_log, [...values, id]);
  return getLogById(id);
}

function deleteLog(id) {
  runQuery(sql.queries.delete_log, [id]);
  return { deleted: true };
}

function getStats(params = {}) {
  const { where, values } = buildWhere(params);

  const overview = getRun(sql.queries.stats_overview + where, values);

  const dailyStats = runQuery(sql.queries.stats_daily + where + ' ' + sql.queries.group_by_date, values);

  const driverStats = runQuery(sql.queries.stats_by_driver + where + ' AND driver != \'\' ' + sql.queries.group_by_driver_limit, values);

  return { overview, dailyStats, driverStats };
}

module.exports = { getDb, getAllLogs, getLogById, createLog, updateLog, deleteLog, getStats };
