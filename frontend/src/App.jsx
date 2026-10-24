import { useEffect, useMemo, useRef, useState } from "react";
import { api, setAccountScope } from "./api.js";
import { cls, daysSince, fmtPct, fmtPln, fmtNum } from "./format.js";
import { portfolioStructureTotal, positionStructureValue } from "./portfolioStructure.js";
import HistoryChart from "./components/HistoryChart.jsx";
import DrawdownChart from "./components/DrawdownChart.jsx";
import InstrumentDetail from "./components/InstrumentDetail.jsx";
import PositionsTable from "./components/PositionsTable.jsx";
import TransactionForm from "./components/TransactionForm.jsx";
import BondForm from "./components/BondForm.jsx";
import TransactionsTable from "./components/TransactionsTable.jsx";
import CashPanel, { CashForm } from "./components/CashPanel.jsx";
import InstrumentsPanel from "./components/InstrumentsPanel.jsx";
import AllocationPanel from "./components/AllocationPanel.jsx";
import DailyChangesTable from "./components/DailyChangesTable.jsx";
import ReturnsStrip from "./components/ReturnsStrip.jsx";
import DataPanel from "./components/DataPanel.jsx";
import DataQualityPanel from "./components/DataQualityPanel.jsx";
import RebalancePlanner from "./components/RebalancePlanner.jsx";
import AnalyticsBreakdown from "./components/AnalyticsBreakdown.jsx";
import ReportsPanel from "./components/ReportsPanel.jsx";
import BrokerMappingModal from "./components/BrokerMappingModal.jsx";
import AccountSelect from "./components/AccountSelect.jsx";
import AccountsPanel from "./components/AccountsPanel.jsx";
import Modal from "./components/Modal.jsx";

// Pięć sekcji od najczęściej do najrzadziej używanej; pod-zakładki żyją w SUBS.
const NAV = [
  ["overview", "Przegląd"],
  ["portfolio", "Portfel"],
  ["history", "Historia"],
  ["analysis", "Raporty"],
  ["settings", "Ustawienia"],
];

const SUBS = {
  portfolio: [["positions", "Pozycje"], ["allocation", "Alokacja"]],
  history: [["transactions", "Transakcje"], ["cash", "Wpłaty i wypłaty"]],
  analysis: [["report", "Raport okresowy"], ["performance", "Wynik i atrybucja"], ["risk", "Ryzyko"], ["daily", "Zmiany dzienne"]],
  settings: [["quality", "Jakość danych"], ["instruments", "Instrumenty"], ["accounts", "Konta"], ["data", "Synchronizacja i kopie"]],
};

// Stare linki (?tab=…) prowadzą w nowe miejsce: [strona, pod-zakładka].
const LEGACY_TABS = {
  dashboard: ["overview"],
  activity: ["history", "transactions"],
  transactions: ["history", "transactions"],
  cash: ["history", "cash"],
  allocation: ["portfolio", "allocation"],
  daily: ["analysis", "daily"],
  instruments: ["settings", "instruments"],
};

const ADD_TABS = [
  ["tx", "Transakcja"],
  ["bond", "Obligacje"],
  ["cash", "Wpłata / wypłata"],
  ["import", "Import z pliku"],
];

function initialRoute() {
  const fromUrl = new URLSearchParams(window.location.search).get("tab");
  if (LEGACY_TABS[fromUrl]) return LEGACY_TABS[fromUrl];
  return NAV.some(([id]) => id === fromUrl) ? [fromUrl] : ["overview"];
}

// Widok konta żyje w URL (?account=), żeby odświeżenie strony go nie gubiło. 0 = cały portfel.
function initialAccount() {
  const id = Number(new URLSearchParams(window.location.search).get("account")) || 0;
  setAccountScope(id);
  return id;
}

const DATE_FMT = new Intl.DateTimeFormat("pl-PL", { day: "numeric", month: "long", year: "numeric" });
const fmtDay = (iso) => (iso ? DATE_FMT.format(new Date(`${iso.slice(0, 10)}T12:00:00`)) : "—");

// Odmiana: 1 transakcja, 2–4 transakcje, 5+ transakcji (z wyjątkiem 12–14).
const plural = (n, one, few, many) => {
  if (n === 1) return one;
  const tens = n % 100;
  return n % 10 >= 2 && n % 10 <= 4 && (tens < 12 || tens > 14) ? few : many;
};

function Kpi({ label, value, detail, tone }) {
  return (
    <div className="kpi">
      <span className="kpi-label">{label}</span>
      <strong className={`kpi-value ${tone || ""}`}>{value}</strong>
      {detail && <span className="kpi-detail">{detail}</span>}
    </div>
  );
}

// Zakładki zgodne z wzorcem WAI-ARIA: strzałki przenoszą wybór, Tab wychodzi z listy.
function Tabs({ items, value, onChange, label, children }) {
  const onKey = (e) => {
    const index = items.findIndex(([id]) => id === value);
    const step = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
    if (!step) return;
    e.preventDefault();
    const next = items[(index + step + items.length) % items.length][0];
    onChange(next);
    e.currentTarget.querySelector(`[data-tab="${next}"]`)?.focus();
  };
  return (
    <div className="tabs-row">
      <div className="tabs" role="tablist" aria-label={label} onKeyDown={onKey}>
        {items.map(([id, text]) => (
          <button
            key={id}
            data-tab={id}
            role="tab"
            aria-selected={value === id}
            tabIndex={value === id ? 0 : -1}
            onClick={() => onChange(id)}
          >
            {text}
          </button>
        ))}
      </div>
      {children}
    </div>
  );
}

function Block({ title, action, children, className = "" }) {
  return (
    <section className={`block ${className}`}>
      <header className="block-head">
        <h2>{title}</h2>
        {action}
      </header>
      {children}
    </section>
  );
}

export default function App() {
  const [portfolio, setPortfolio] = useState(null);
  const [history, setHistory] = useState([]);
  const [instruments, setInstruments] = useState([]);
  const [transactions, setTransactions] = useState([]);
  const [cash, setCash] = useState(null);
  const [allocation, setAllocation] = useState(null);
  const [dailyChanges, setDailyChanges] = useState([]);
  const [drawdown, setDrawdown] = useState(null);
  const [backups, setBackups] = useState(null);
  const [quality, setQuality] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [detail, setDetail] = useState(null);
  const [accounts, setAccounts] = useState([]);
  const [account, setAccount] = useState(initialAccount);
  const [importAccount, setImportAccount] = useState(null);
  const [route, setRoute] = useState(initialRoute);
  const [subs, setSubs] = useState({ portfolio: "positions", history: "transactions", analysis: "report", settings: "quality" });
  const [adding, setAdding] = useState(null);
  const [benchmarkRate, setBenchmarkRate] = useState(5);
  const [cpiSpread, setCpiSpread] = useState(2);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState(null);
  const [pendingImport, setPendingImport] = useState(null);
  const fileRef = useRef();
  const flashTimer = useRef();
  const page = route[0];
  const sub = route[1] || subs[page];

  const flash = (text, ok = true) => {
    window.clearTimeout(flashTimer.current);
    setMsg({ text, ok });
    flashTimer.current = window.setTimeout(() => setMsg(null), 5000);
  };

  const loadAll = async () => {
    const [pf, hist, insts, txs, cs, alloc, daily, dd, bk, dq, analysis, accs] = await Promise.all([
      api.portfolio(),
      api.history(benchmarkRate / 100, cpiSpread / 100),
      api.instruments(),
      api.transactions(),
      api.cash(),
      api.allocation(),
      api.dailyChanges(),
      api.drawdown(),
      api.backups(),
      api.dataQuality(),
      api.analytics(),
      api.accounts(),
    ]);
    setPortfolio(pf);
    setHistory(hist);
    setInstruments(insts);
    setTransactions(txs);
    setCash(cs);
    setAllocation(alloc);
    setDailyChanges(daily);
    setDrawdown(dd);
    setBackups(bk);
    setQuality(dq);
    setAnalytics(analysis);
    setAccounts(accs);
  };

  useEffect(() => {
    loadAll()
      .catch((e) => flash(`Nie udało się załadować danych: ${e.message}`, false))
      .finally(() => setLoading(false));
    return () => window.clearTimeout(flashTimer.current);
  }, []);

  useEffect(() => {
    const onPopState = () => setRoute(initialRoute());
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      api.history(benchmarkRate / 100, cpiSpread / 100).then(setHistory).catch(() => {});
    }, 350);
    return () => window.clearTimeout(timer);
  }, [benchmarkRate, cpiSpread]);

  // `next` to sekcja, `subId` — opcjonalna pod-zakładka (ostrzeżenia prowadzą prosto do miejsca naprawy).
  const navigate = (next, subId) => {
    if (subId) setSubs((current) => ({ ...current, [next]: subId }));
    setRoute([next]);
    const url = new URL(window.location.href);
    url.searchParams.set("tab", next);
    window.history.pushState({}, "", url);
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    window.scrollTo({ top: 0, behavior: reduce ? "auto" : "smooth" });
  };
  const setSub = (id) => {
    setSubs((current) => ({ ...current, [page]: id }));
    setRoute([page]);
  };

  const run = async (fn, okMsg) => {
    setBusy(true);
    try {
      const result = await fn();
      await loadAll();
      if (okMsg) flash(typeof okMsg === "function" ? okMsg(result) : okMsg);
      return result;
    } catch (e) {
      flash(`Nie udało się wykonać operacji: ${e.message}`, false);
      throw e;
    } finally {
      setBusy(false);
    }
  };

  const changeAccount = (id) => {
    setAccountScope(id);
    setAccount(id);
    const url = new URL(window.location.href);
    if (id) url.searchParams.set("account", id); else url.searchParams.delete("account");
    window.history.replaceState({}, "", url);
    run(() => Promise.resolve()).catch(() => {});
  };
  // Konto dla nowych operacji: oglądane, a w widoku całego portfela — pierwsze z listy.
  const defaultAccount = account || accounts[0]?.id;
  const targetImportAccount = importAccount || defaultAccount;

  const openDetail = (isin) => {
    api.instrumentHistory(isin).then(setDetail).catch((e) => flash(`Nie udało się otworzyć instrumentu: ${e.message}`, false));
  };

  const onImportPrices = (isin, file) => {
    let currency = detail?.currency;
    if (!currency) {
      currency = window.prompt(
        "Podaj walutę cen z tego pliku (np. PLN, USD, EUR, GBP):",
        "PLN",
      );
      if (!currency) return;
    }
    run(
      () => api.importPrices(isin, file, currency.trim().toUpperCase()),
      (r) => `Wczytano ${r.imported} cen z okresu ${r.first_date} – ${r.last_date}.`,
    ).then(() => api.instrumentHistory(isin).then(setDetail)).catch(() => {});
  };

  const importSuccessMessage = (result) => {
    const formats = {
      emakler_current: "eMAKLER",
      legacy_hispw: "historia PW",
      mbank_confirmation_pdf: "potwierdzenie PDF mBank",
    };
    const enriched = result.enriched ? ` Uzupełniono metadane ${result.enriched} istniejących transakcji.` : "";
    return `Format: ${formats[result.format] || result.format}. Zaimportowano ${result.imported} transakcji. Pominięte duplikaty: ${result.skipped_duplicates}.${enriched}`;
  };

  const importFile = async (file) => {
    setBusy(true);
    try {
      const result = await api.importTransactions(file, targetImportAccount);
      await loadAll();
      setAdding(null);
      flash(importSuccessMessage(result));
    } catch (error) {
      if (error.detail?.code === "broker_mapping_required") {
        setPendingImport({ file, instruments: error.detail.instruments });
      } else {
        flash(`Nie udało się wykonać operacji: ${error.message}`, false);
      }
    } finally {
      setBusy(false);
    }
  };

  const saveMappingsAndImport = async (mappings) => {
    if (!pendingImport) return;
    setBusy(true);
    try {
      await api.saveBrokerInstrumentMappings(mappings);
      const result = await api.importTransactions(pendingImport.file, targetImportAccount);
      setPendingImport(null);
      setAdding(null);
      await loadAll();
      flash(importSuccessMessage(result));
    } catch (error) {
      flash(`Nie udało się zapisać mapowania: ${error.message}`, false);
    } finally {
      setBusy(false);
    }
  };

  const onImport = (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    importFile(file);
    event.target.value = "";
  };

  const totals = portfolio?.totals || {};
  // Jedna kolejność pozycji w całej aplikacji: od największej wartości.
  const positions = useMemo(
    () => [...(portfolio?.positions || [])].sort((a, b) => (b.value_pln || 0) - (a.value_pln || 0)),
    [portfolio],
  );
  const accountValue = totals.portfolio_value_pln ?? totals.value_pln ?? totals.value_pln_partial;
  const latestDaily = dailyChanges.length ? dailyChanges[dailyChanges.length - 1] : null;
  const latestPriceDate = useMemo(
    () => positions.map((p) => p.price_date).filter(Boolean).sort().at(-1),
    [positions],
  );
  const staleCount = positions.filter((p) => (daysSince(p.price_date) ?? 0) > 4).length;
  // Ostatni punkt z oboma seriami — różnica to przewaga nad inflacją + premia, w punktach procentowych.
  const vsInflation = useMemo(() => {
    const row = [...history].reverse().find((r) => r.portfolio_pct != null && r.benchmark_cpi_pct != null);
    return row ? row.portfolio_pct - row.benchmark_cpi_pct : null;
  }, [history]);
  const structureTotal = portfolioStructureTotal(positions, totals.cash_pln);
  const issues = quality?.summary?.issues || 0;

  if (loading) {
    return (
      <div className="boot-screen" role="status">
        <strong>Portfolio</strong>
        <span>Wczytuję dane portfela…</span>
      </div>
    );
  }

  const dataStatus = issues || staleCount ? (
    <button className="status-link warn" onClick={() => navigate("settings", staleCount ? "data" : "quality")}>
      {staleCount
        ? `${staleCount} ${plural(staleCount, "nieaktualna wycena", "nieaktualne wyceny", "nieaktualnych wycen")}`
        : `${issues} ${plural(issues, "uwaga", "uwagi", "uwag")} do danych`}
    </button>
  ) : <span className="status-link">Dane aktualne</span>;

  const Overview = (
    <>
      <header className="page-head">
        <div>
          <h1>Przegląd</h1>
          <p className="page-sub">Wyceny z {fmtDay(latestPriceDate)} · {dataStatus}</p>
        </div>
        <button className="secondary" onClick={() => run(() => api.refresh(), "Wyceny zostały odświeżone.").catch(() => {})} disabled={busy}>
          {busy ? "Odświeżam…" : "Odśwież wyceny"}
        </button>
      </header>

      <div className="kpis">
        <Kpi
          label="Wartość portfela"
          value={fmtPln(accountValue)}
          detail={totals.tax_pln > 0 ? `Po podatku ${fmtPln(totals.value_after_tax_pln)}` : `Gotówka ${fmtPln(totals.cash_pln)}`}
        />
        <Kpi
          label="Zysk od początku"
          value={fmtPln(totals.total_pl_pln)}
          tone={cls(totals.total_pl_pln)}
          detail={totals.twr == null ? null : `TWR ${fmtPct(totals.twr * 100)}`}
        />
        <Kpi
          label="Ostatnia sesja"
          value={latestDaily ? fmtPln(latestDaily.change_pln) : "—"}
          tone={cls(latestDaily?.change_pln)}
          detail={latestDaily?.change_pct == null ? null : fmtPct(latestDaily.change_pct)}
        />
        <Kpi
          label={`Ponad inflację +${cpiSpread}%`}
          value={vsInflation == null ? "—" : `${vsInflation > 0 ? "+" : ""}${fmtNum(vsInflation, 1)} pp`}
          tone={cls(vsInflation)}
          detail={totals.xirr == null ? null : `XIRR ${fmtPct(totals.xirr * 100)} rocznie`}
        />
      </div>

      <div className="split">
        <Block title="Wartość w czasie" action={<button className="text-button" onClick={() => navigate("analysis", "performance")}>Pełna analiza</button>}>
          <HistoryChart data={history} benchmarkRate={benchmarkRate} cpiSpread={cpiSpread} compact />
        </Block>
        <Block title="Największe pozycje" action={<button className="text-button" onClick={() => navigate("portfolio", "positions")}>Cały portfel</button>}>
          {positions.length ? (
            <ol className="rank-list">
              {positions.slice(0, 6).map((p) => (
                <li key={p.isin}>
                  <button className="instrument-link" onClick={() => openDetail(p.isin)}>{p.name}</button>
                  <span className="muted">{structureTotal ? `${fmtNum(positionStructureValue(p) / structureTotal * 100, 1)}%` : ""}</span>
                  <span>{fmtPln(p.value_pln)}</span>
                </li>
              ))}
            </ol>
          ) : <p className="empty">Brak pozycji. Dodaj transakcję albo zaimportuj plik z biura maklerskiego.</p>}
        </Block>
      </div>
    </>
  );

  const Portfolio = (
    <>
      <header className="page-head"><h1>Portfel</h1></header>
      <div className="kpis">
        <Kpi
          label="Wartość pozycji"
          value={fmtPln(totals.value_pln ?? totals.value_pln_partial)}
          detail={`${positions.length} ${plural(positions.length, "pozycja", "pozycje", "pozycji")} · gotówka ${fmtPln(totals.cash_pln)}`}
        />
        <Kpi label="Koszt" value={fmtPln(totals.cost_pln)} detail="Kapitał w otwartych pozycjach" />
        <Kpi
          label="Zysk niezrealizowany"
          value={fmtPln(totals.unrealized_pl_pln)}
          tone={cls(totals.unrealized_pl_pln)}
          detail={totals.pl_pct == null ? null : fmtPct(totals.pl_pct)}
        />
        <Kpi
          label="Zysk zrealizowany"
          value={fmtPln(totals.realized_pl_pln)}
          tone={cls(totals.realized_pl_pln)}
          detail={totals.tax_pln > 0 ? `Podatek przy sprzedaży dziś ${fmtPln(totals.tax_pln)}` : "Zamknięte transakcje"}
        />
      </div>
      <Tabs items={SUBS.portfolio} value={sub} onChange={setSub} label="Widok portfela" />
      {sub === "positions" && (
        <Block title="Pozycje">
          <PositionsTable positions={positions} totals={totals} onOpen={openDetail} onConfigure={() => navigate("settings", "instruments")} />
        </Block>
      )}
      {sub === "allocation" && (
        <>
          <Block title="Alokacja docelowa i rzeczywista">
            <AllocationPanel
              allocation={allocation}
              onSave={(targets) => run(() => api.setAllocation(targets), "Model docelowy został zapisany.").catch(() => {})}
            />
          </Block>
          <Block title="Rebalancing nową wpłatą">
            <RebalancePlanner allocation={allocation} onPlan={(amount) => api.contributionPlan(amount)} />
          </Block>
        </>
      )}
    </>
  );

  const flows = cash?.flows?.length || 0;
  const History = (
    <>
      <header className="page-head">
        <h1>Historia</h1>
        <a className="secondary" href="/api/export/transactions.csv">Eksportuj CSV</a>
      </header>
      <Tabs items={SUBS.history} value={sub} onChange={setSub} label="Rodzaj operacji" />
      {sub === "transactions" && (
        <Block title={`Transakcje (${transactions.length})`}>
        <TransactionsTable
          transactions={transactions}
          instruments={instruments}
          accounts={accounts}
          onOpen={openDetail}
          onUpdate={(id, body) => run(
            () => api.updateTransaction(id, body),
            "Transakcja została zaktualizowana.",
          )}
          onDelete={(id) => {
            if (window.confirm("Usunąć tę transakcję? Wpłynie to na wycenę i historię portfela.")) {
              run(() => api.deleteTransaction(id), "Transakcja została usunięta.").catch(() => {});
            }
          }}
        />
        </Block>
      )}
      {sub === "cash" && (
        <Block title="Wpłaty i wypłaty">
        <CashPanel
          cash={cash}
          accounts={accounts}
          onDelete={(id) => {
            if (window.confirm("Usunąć tę operację gotówkową?")) {
              run(() => api.deleteCash(id), "Operacja została usunięta.").catch(() => {});
            }
          }}
        />
        </Block>
      )}
    </>
  );

  const Analysis = (
    <>
      <header className="page-head no-print"><h1>Raporty</h1></header>
      <Tabs items={SUBS.analysis} value={sub} onChange={setSub} label="Widok raportów">
        <div className="benchmark-fields no-print">
          <label>Stała stopa <input type="number" step="0.5" value={benchmarkRate} onChange={(e) => setBenchmarkRate(parseFloat(e.target.value) || 0)} /> %</label>
          <label>Inflacja + <input type="number" step="0.5" value={cpiSpread} onChange={(e) => setCpiSpread(parseFloat(e.target.value) || 0)} /> %</label>
        </div>
      </Tabs>

      {sub === "report" && <ReportsPanel key={account} benchmarkRate={benchmarkRate} cpiSpread={cpiSpread} onOpen={openDetail} />}

      {sub === "performance" && (
        <>
          <ReturnsStrip returns={totals.returns} />
          <Block title="Wartość i stopa zwrotu">
            <HistoryChart data={history} benchmarkRate={benchmarkRate} cpiSpread={cpiSpread} />
          </Block>
          <Block title="Co buduje wynik">
            <AnalyticsBreakdown analytics={analytics} allocation={allocation} onOpen={openDetail} />
          </Block>
        </>
      )}

      {sub === "risk" && (
        <Block title="Obsunięcie od szczytu">
          <DrawdownChart data={drawdown} />
        </Block>
      )}

      {sub === "daily" && (
        <Block title="Zmiany wartości dzień po dniu" action={<a className="text-button" href="/api/export/daily-changes.csv">Eksportuj CSV</a>}>
          <DailyChangesTable rows={dailyChanges} />
        </Block>
      )}
    </>
  );

  const Settings = (
    <>
      <header className="page-head"><h1>Ustawienia</h1></header>
      <Tabs items={SUBS.settings} value={sub} onChange={setSub} label="Sekcja ustawień" />

      {sub === "quality" && (
        <Block title="Jakość danych">
        <DataQualityPanel
          quality={quality}
          busy={busy}
          onRefresh={() => run(() => api.dataQuality(), "Kontrola jakości została odświeżona.").catch(() => {})}
          onGo={navigate}
        />
        </Block>
      )}

      {sub === "instruments" && (
        <Block title="Nazwy i mapowanie notowań">
          <InstrumentsPanel
            instruments={instruments}
            onSave={(isin, body) => run(() => api.updateInstrument(isin, body), "Ustawienia instrumentu zostały zapisane.")}
          />
        </Block>
      )}

      {sub === "accounts" && (
        <Block title="Konta inwestycyjne">
          <p className="block-note">Konta opodatkowane: szacunek 19% podatku od zysków. IKE i IKZE zostaw bez podatku.</p>
          <AccountsPanel
            accounts={accounts}
            busy={busy}
            onSave={(id, body) => run(() => api.saveAccount(id, body), "Konto zostało zapisane.").catch(() => {})}
          />
        </Block>
      )}

      {sub === "data" && (
        <>
          <Block title="Źródła danych">
            <div className="sync-list">
              <div className="sync-item">
                <div>
                  <strong>Wyceny i kursy NBP</strong>
                  <p>{latestPriceDate ? `Ostatnie dane z ${fmtDay(latestPriceDate)}. ` : ""}Ceny z Yahoo, EODHD lub Alpha Vantage, z uzupełnieniem krótkich luk.</p>
                </div>
                <button className="secondary" disabled={busy} onClick={() => run(() => api.refresh(), "Wyceny zostały odświeżone.").catch(() => {})}>Odśwież</button>
              </div>
              <div className="sync-item">
                <div>
                  <strong>Pełna historia wycen</strong>
                  <p>Odbudowuje dane potrzebne do wykresów i analizy.</p>
                </div>
                <button className="secondary" disabled={busy} onClick={() => run(() => api.backfill(), "Historia wycen została uzupełniona.").catch(() => {})}>Uzupełnij</button>
              </div>
              <div className="sync-item">
                <div>
                  <strong>Inflacja (Eurostat HICP dla Polski)</strong>
                  <p>Aktualizuje benchmark „inflacja + premia”.</p>
                </div>
                <button className="secondary" disabled={busy} onClick={() => run(() => api.refreshCpi(), "Dane inflacyjne zostały odświeżone.").catch(() => {})}>Pobierz</button>
              </div>
            </div>
          </Block>
          <Block title="Kopie zapasowe i eksport">
            <DataPanel
              backups={backups}
              busy={busy}
              onBackup={() => run(() => api.backupNow(), "Kopia zapasowa została utworzona.").catch(() => {})}
              onRestore={(filename) => run(
                () => api.restoreBackup(filename),
                (result) => `Baza została przywrócona. Kopia bezpieczeństwa: ${result.safety_backup}.`,
              ).catch(() => {})}
              onRestoreUpload={(file) => run(
                () => api.restoreUploadedBackup(file),
                (result) => `Baza została przywrócona z pliku. Kopia bezpieczeństwa: ${result.safety_backup}.`,
              ).catch(() => {})}
            />
          </Block>
        </>
      )}
    </>
  );

  const pages = { overview: Overview, portfolio: Portfolio, history: History, analysis: Analysis, settings: Settings };

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-inner">
          <button className="brand" onClick={() => navigate("overview")}>Portfolio</button>
          <nav className="main-nav" aria-label="Główna nawigacja">
            {NAV.map(([id, label]) => (
              <button key={id} className={page === id ? "active" : ""} onClick={() => navigate(id)} aria-current={page === id ? "page" : undefined}>
                {label}
              </button>
            ))}
          </nav>
          <div className="topbar-tools">
            {accounts.length > 1 && (
              <select className="cell account-select" aria-label="Widok konta" value={account} onChange={(e) => changeAccount(Number(e.target.value))}>
                <option value={0}>Cały portfel</option>
                {accounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
              </select>
            )}
            <button className="primary" onClick={() => setAdding("tx")}>Dodaj</button>
          </div>
        </div>
        {busy && <div className="progress-line" role="progressbar" aria-label="Trwa aktualizacja" />}
      </header>

      <main className="main-content">{pages[page]}</main>

      <div className="toast-region" role="status" aria-live="polite">
        {msg && <div className={`toast ${msg.ok ? "ok" : "err"}`}>{msg.text}</div>}
      </div>

      <input ref={fileRef} type="file" accept=".csv,.pdf,application/pdf" className="hidden-file" onChange={onImport} />
      {adding && (
        <Modal label="Dodaj" className="add-modal" onClose={() => setAdding(null)}>
          <div className="modal-head">
            <h2>Dodaj</h2>
            <div className="modal-actions"><button onClick={() => setAdding(null)}>Zamknij</button></div>
          </div>
          <Tabs items={ADD_TABS} value={adding} onChange={setAdding} label="Co chcesz dodać" />
          {adding === "tx" && (
            <>
              <p className="add-hint">Zakup lub sprzedaż wprowadzona ręcznie.</p>
              <TransactionForm
                key={account}
                instruments={instruments}
                accounts={accounts}
                defaultAccount={defaultAccount}
                onAdd={(body) => run(
                  () => api.addTransaction(body),
                  (r) => r.created ? "Transakcja została dodana." : "Taka transakcja już istnieje.",
                ).catch(() => {})}
              />
            </>
          )}
          {adding === "bond" && (
            <>
              <p className="add-hint">EDO, TOS, ROS i ROD — wycena z tabel odsetkowych Ministerstwa Finansów. Wykup dodaj jako sprzedaż.</p>
              <BondForm
                key={account}
                accounts={accounts}
                defaultAccount={defaultAccount}
                busy={busy}
                onAdd={(body) => run(
                  () => api.addBondPurchase(body),
                  (r) => r.created ? "Obligacje zostały dodane." : "Taki zakup już istnieje.",
                ).catch(() => {})}
                onImportTable={(file) => run(
                  () => api.importBondTable(file),
                  (r) => `Wczytano tabelę ${r.series}: ${r.first_date} – ${r.last_date}.`,
                ).catch(() => {})}
              />
            </>
          )}
          {adding === "cash" && (
            <>
              <p className="add-hint">Wpłata lub wypłata gotówki z konta inwestycyjnego.</p>
              <CashForm
                key={account}
                accounts={accounts}
                defaultAccount={defaultAccount}
                onAdd={(body) => run(() => api.addCash(body), "Operacja gotówkowa została dodana.").catch(() => {})}
              />
            </>
          )}
          {adding === "import" && (
            <>
              <p className="add-hint">Obsługuje CSV „historia PW”, eMAKLER „Transakcje bieżące” oraz potwierdzenia PDF mBanku. Format jest rozpoznawany automatycznie.</p>
              <div className="tx-form">
                <AccountSelect label="Konto" accounts={accounts} value={targetImportAccount} onChange={setImportAccount} />
                <button className="secondary" onClick={() => fileRef.current?.click()} disabled={busy}>Wybierz plik CSV lub PDF</button>
              </div>
            </>
          )}
        </Modal>
      )}
      {detail && (
        <InstrumentDetail
          data={detail}
          busy={busy}
          onImportPrices={onImportPrices}
          onClose={() => setDetail(null)}
        />
      )}
      {pendingImport && (
        <BrokerMappingModal
          instruments={pendingImport.instruments}
          filename={pendingImport.file.name}
          busy={busy}
          onCancel={() => setPendingImport(null)}
          onSave={saveMappingsAndImport}
        />
      )}
    </div>
  );
}
