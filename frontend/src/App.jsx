import { useEffect, useRef, useState } from "react";
import { api } from "./api.js";
import Cards from "./components/Cards.jsx";
import ReturnsStrip from "./components/ReturnsStrip.jsx";
import HistoryChart from "./components/HistoryChart.jsx";
import InstrumentDetail from "./components/InstrumentDetail.jsx";
import PositionsTable from "./components/PositionsTable.jsx";
import TransactionForm from "./components/TransactionForm.jsx";
import TransactionsTable from "./components/TransactionsTable.jsx";
import CashPanel from "./components/CashPanel.jsx";
import InstrumentsPanel from "./components/InstrumentsPanel.jsx";
import AllocationPanel from "./components/AllocationPanel.jsx";
import BackupModal from "./components/BackupModal.jsx";
import DailyChangesTable from "./components/DailyChangesTable.jsx";

const TABS = [
  ["dashboard", "Pulpit"],
  ["daily", "Zmiany dzienne"],
  ["transactions", "Transakcje"],
  ["allocation", "Alokacja"],
  ["cash", "Gotówka"],
  ["instruments", "Instrumenty"],
];

export default function App() {
  const [portfolio, setPortfolio] = useState(null);
  const [history, setHistory] = useState([]);
  const [instruments, setInstruments] = useState([]);
  const [transactions, setTransactions] = useState([]);
  const [cash, setCash] = useState(null);
  const [allocation, setAllocation] = useState(null);
  const [dailyChanges, setDailyChanges] = useState([]);
  const [backups, setBackups] = useState(null);
  const [showBackup, setShowBackup] = useState(false);
  const [detail, setDetail] = useState(null);
  const [tab, setTab] = useState(() => new URLSearchParams(window.location.search).get("tab") || "dashboard");
  const [benchmarkRate, setBenchmarkRate] = useState(5);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const fileRef = useRef();

  const flash = (text, ok = true) => {
    setMsg({ text, ok });
    setTimeout(() => setMsg(null), 5000);
  };

  const loadAll = async () => {
    const [pf, hist, insts, txs, cs, alloc, daily, bk] = await Promise.all([
      api.portfolio(), api.history(benchmarkRate / 100), api.instruments(), api.transactions(), api.cash(), api.allocation(), api.dailyChanges(), api.backups(),
    ]);
    setPortfolio(pf); setHistory(hist); setInstruments(insts); setTransactions(txs); setCash(cs); setAllocation(alloc); setDailyChanges(daily); setBackups(bk);
  };

  useEffect(() => {
    loadAll().catch((e) => flash(`Błąd ładowania: ${e.message}`, false));
  }, []);

  // Przeładuj samą historię po zmianie stopy benchmarku.
  useEffect(() => {
    api.history(benchmarkRate / 100).then(setHistory).catch(() => {});
  }, [benchmarkRate]);

  const run = async (fn, okMsg) => {
    setBusy(true);
    try {
      await fn();
      await loadAll();
      if (okMsg) flash(okMsg);
    } catch (e) {
      flash(`Błąd: ${e.message}`, false);
    } finally {
      setBusy(false);
    }
  };

  const openDetail = (isin) => {
    api.instrumentHistory(isin).then(setDetail).catch((e) => flash(`Błąd: ${e.message}`, false));
  };

  const onImportPrices = (isin, file) => {
    // Waluta jest potrzebna do wyceny, a CSV jej nie niesie. Jeśli instrument ją ma —
    // używamy jej; jeśli nie — pytamy (NIE zgadujemy PLN, bo stooq notuje też w USD/EUR/GBP).
    let currency = detail?.currency;
    if (!currency) {
      currency = window.prompt(
        "Instrument nie ma ustawionej waluty. Podaj walutę cen z tego CSV (np. PLN, USD, EUR, GBP):",
        "PLN",
      );
      if (!currency) return; // anulowano
    }
    run(async () => {
      const r = await api.importPrices(isin, file, currency.trim().toUpperCase());
      flash(`Wczytano ${r.imported} cen (${r.first_date} – ${r.last_date}). Waluta: ${r.currency}.`);
      setDetail(await api.instrumentHistory(isin));  // odśwież otwarty modal
    });
  };

  const onImport = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    run(async () => {
      const r = await api.importCsv(file);
      flash(`Zaimportowano ${r.imported} transakcji (pominięto duplikatów: ${r.skipped_duplicates}).`);
    });
    e.target.value = "";
  };

  return (
    <div className="app">
      <header className="top">
        <div>
          <h1>Portfolio Tracker</h1>
          <div className="sub">Self-hosted · wyceny w PLN (przeliczane kursem NBP)</div>
        </div>
        <div className="toolbar">
          <input ref={fileRef} type="file" accept=".csv" className="hidden-file" onChange={onImport} />
          <button onClick={() => fileRef.current?.click()} disabled={busy}>Importuj CSV</button>
          <button onClick={() => run(() => api.refresh(), "Odświeżono ceny i kursy.")} disabled={busy}>Odśwież ceny</button>
          <button onClick={() => run(() => api.backfill(), "Pobrano historię wycen.")} disabled={busy}>Backfill historii</button>
          <button onClick={() => setShowBackup(true)} disabled={busy}>Backup</button>
        </div>
      </header>

      {msg && <div className={`msg ${msg.ok ? "ok" : "err"}`}>{msg.text}</div>}
      {busy && <div className="spinner">Pracuję…</div>}

      <Cards totals={portfolio?.totals} />

      <nav className="tabs">
        {TABS.map(([id, label]) => (
          <button key={id} className={`tab ${tab === id ? "active" : ""}`} onClick={() => setTab(id)}>
            {label}
            {id === "transactions" && transactions.length ? <span className="count">{transactions.length}</span> : null}
          </button>
        ))}
      </nav>

      {tab === "dashboard" && (
        <>
          <ReturnsStrip returns={portfolio?.totals?.returns} />
          <div className="panel">
            <div className="panel-head">
              <h2>Wartość konta vs benchmark</h2>
              <label className="bench-ctrl">
                Benchmark:
                <input
                  type="number"
                  step="0.5"
                  className="cell narrow"
                  value={benchmarkRate}
                  onChange={(e) => setBenchmarkRate(parseFloat(e.target.value) || 0)}
                />
                % rocznie
              </label>
            </div>
            <HistoryChart data={history} />
          </div>
          <div className="panel">
            <h2>Pozycje</h2>
            <PositionsTable positions={portfolio?.positions} totals={portfolio?.totals || {}} onOpen={openDetail} />
          </div>
        </>
      )}

      {tab === "daily" && (
        <div className="panel">
          <div className="panel-head">
            <h2>Zmiany dzienne (zysk/strata D/D)</h2>
            <a className="btn" href="/api/export/daily-changes.csv">⬇ Eksport CSV</a>
          </div>
          <div className="sub" style={{ marginBottom: 12 }}>
            Zmiana to wynik <strong>rynkowy</strong> dnia (sama wycena ETF) — koszt kupna/sprzedaży jest
            odjęty, więc zakup nie liczy się jako zysk. Gotówka pominięta (nie ma stopy zwrotu).
          </div>
          <DailyChangesTable rows={dailyChanges} />
        </div>
      )}

      {tab === "transactions" && (
        <div className="panel">
          <h2>Historia transakcji</h2>
          <TransactionForm
            instruments={instruments}
            onAdd={(body) => run(async () => {
              const r = await api.addTransaction(body);
              flash(r.created ? "Dodano transakcję." : "Pominięto — taka transakcja już istnieje.", r.created);
            })}
          />
          <TransactionsTable
            transactions={transactions}
            onOpen={openDetail}
            onDelete={(id) => run(() => api.deleteTransaction(id), "Usunięto transakcję.")}
          />
        </div>
      )}

      {tab === "allocation" && (
        <div className="panel">
          <h2>Alokacja docelowa vs rzeczywista</h2>
          <AllocationPanel
            allocation={allocation}
            onSave={(targets) => run(() => api.setAllocation(targets), "Zapisano model docelowy.")}
          />
        </div>
      )}

      {tab === "cash" && (
        <div className="panel">
          <h2>Konto gotówkowe</h2>
          <CashPanel
            cash={cash}
            onAdd={(body) => run(() => api.addCash(body), "Dodano operację gotówkową.")}
            onDelete={(id) => run(() => api.deleteCash(id), "Usunięto operację.")}
          />
        </div>
      )}

      {tab === "instruments" && (
        <div className="panel">
          <h2>Instrumenty (mapowanie ISIN → ticker)</h2>
          <InstrumentsPanel
            instruments={instruments}
            onSave={(isin, body) => run(() => api.updateInstrument(isin, body), "Zapisano mapowanie.")}
          />
        </div>
      )}

      {showBackup && (
        <BackupModal
          backups={backups}
          busy={busy}
          onBackup={() => run(() => api.backupNow(), "Backup zapisany na serwerze.")}
          onClose={() => setShowBackup(false)}
        />
      )}

      {detail && (
        <InstrumentDetail
          data={detail}
          busy={busy}
          firstTxDate={transactions.filter((t) => t.isin === detail.isin).map((t) => t.ts).sort()[0]}
          onImportPrices={onImportPrices}
          onClose={() => setDetail(null)}
        />
      )}
    </div>
  );
}
