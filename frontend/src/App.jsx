import { useEffect, useMemo, useRef, useState } from "react";
import { api, setAccountScope } from "./api.js";
import { cls, daysSince, fmtPct, fmtPln } from "./format.js";
import HistoryChart from "./components/HistoryChart.jsx";
import HeroSparkline from "./components/HeroSparkline.jsx";
import DrawdownChart from "./components/DrawdownChart.jsx";
import InstrumentDetail from "./components/InstrumentDetail.jsx";
import PositionsTable from "./components/PositionsTable.jsx";
import TransactionForm from "./components/TransactionForm.jsx";
import BondForm from "./components/BondForm.jsx";
import TransactionsTable from "./components/TransactionsTable.jsx";
import CashPanel from "./components/CashPanel.jsx";
import InstrumentsPanel from "./components/InstrumentsPanel.jsx";
import AllocationPanel from "./components/AllocationPanel.jsx";
import AllocationDonut from "./components/AllocationDonut.jsx";
import HoldingsStructureChart from "./components/HoldingsStructureChart.jsx";
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

// Czwarty element to skrót etykiety dla paska mobilnego, gdzie na kafelek przypada ~50 px.
const NAV = [
  ["overview", "Pulpit", "01"],
  ["portfolio", "Portfel", "02"],
  ["activity", "Aktywność", "03"],
  ["allocation", "Alokacja", "04"],
  ["analysis", "Raporty", "05"],
  ["settings", "Dane i ustawienia", "06", "Dane"],
];

const LEGACY_TABS = {
  dashboard: "overview",
  transactions: "activity",
  daily: "activity",
  cash: "portfolio",
  instruments: "settings",
};

const PAGE_META = {
  overview: ["Pulpit", "Najważniejsze informacje o Twoim portfelu"],
  portfolio: ["Portfel", "Pozycje, wyniki i niezainwestowana gotówka"],
  activity: ["Aktywność", "Transakcje i dzienne zmiany wartości"],
  allocation: ["Alokacja", "Kontroluj zgodność portfela z założonym planem"],
  analysis: ["Raporty i analiza", "Wyniki okresowe, benchmarki, atrybucja i ryzyko portfela"],
  settings: ["Dane i ustawienia", "Jakość danych, instrumenty, synchronizacja i kopie zapasowe"],
};

function initialPage() {
  const fromUrl = new URLSearchParams(window.location.search).get("tab");
  const normalized = LEGACY_TABS[fromUrl] || fromUrl;
  return NAV.some(([id]) => id === normalized) ? normalized : "overview";
}

// Widok konta żyje w URL (?account=), żeby odświeżenie strony go nie gubiło. 0 = cały portfel.
function initialAccount() {
  const id = Number(new URLSearchParams(window.location.search).get("account")) || 0;
  setAccountScope(id);
  return id;
}

function SectionHeader({ eyebrow, title, description, action }) {
  return (
    <div className="section-head">
      <div>
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h2>{title}</h2>
        {description && <p>{description}</p>}
      </div>
      {action}
    </div>
  );
}

function Metric({ label, value, detail, tone, featured = false }) {
  return (
    <div className={`metric ${featured ? "featured" : ""}`}>
      <span className="metric-label">{label}</span>
      <strong className={`metric-value ${tone || ""}`}>{value}</strong>
      {detail && <span className="metric-detail">{detail}</span>}
    </div>
  );
}

function StatusDot({ tone = "good", children }) {
  return (
    <span className={`status-chip ${tone}`}>
      <i aria-hidden="true" />
      {children}
    </span>
  );
}

function EmptyAllocation({ onOpen }) {
  return (
    <div className="empty-state compact">
      <span className="empty-mark">A</span>
      <strong>Brak modelu alokacji</strong>
      <p>Przypisz instrumentom kategorie i ustaw docelowe udziały.</p>
      <button className="text-button" onClick={onOpen}>Skonfiguruj alokację</button>
    </div>
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
  const [page, setPage] = useState(initialPage);
  const [structureView, setStructureView] = useState("categories");
  const [analysisView, setAnalysisView] = useState("report");
  const [benchmarkRate, setBenchmarkRate] = useState(5);
  const [cpiSpread, setCpiSpread] = useState(2);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState(null);
  const [pendingImport, setPendingImport] = useState(null);
  const fileRef = useRef();
  const flashTimer = useRef();

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
    const onPopState = () => setPage(initialPage());
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      api.history(benchmarkRate / 100, cpiSpread / 100).then(setHistory).catch(() => {});
    }, 350);
    return () => window.clearTimeout(timer);
  }, [benchmarkRate, cpiSpread]);

  // Otwarty modal ma własny scroll — bez tego tło przewija się pod nim na dotyku.
  useEffect(() => {
    document.body.style.overflow = detail || pendingImport ? "hidden" : "";
    return () => { document.body.style.overflow = ""; };
  }, [detail, pendingImport]);

  const navigate = (next) => {
    setPage(next);
    const url = new URL(window.location.href);
    url.searchParams.set("tab", next);
    window.history.pushState({}, "", url);
    window.scrollTo({ top: 0, behavior: "smooth" });
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
  const allocationGroups = allocation?.groups || [];
  const largestDrift = [...allocationGroups]
    .filter((g) => g.drift_pp != null)
    .sort((a, b) => Math.abs(b.drift_pp) - Math.abs(a.drift_pp))[0];
  const pageMeta = PAGE_META[page] || PAGE_META.overview;

  if (loading) {
    return (
      <div className="boot-screen">
        <div className="brand-mark">P</div>
        <div className="boot-copy">
          <strong>Portfolio</strong>
          <span>Porządkujemy Twoje dane…</span>
        </div>
      </div>
    );
  }

  const Overview = (
    <>
      <section className="hero-grid">
        <div className="hero-card">
          <HeroSparkline data={history} />
          <div className="hero-topline">
            <span>Łączna wartość</span>
            <StatusDot tone={staleCount ? "warn" : "good"}>
              {staleCount ? `${staleCount} nieaktualne wyceny` : `Aktualne ${latestPriceDate || ""}`}
            </StatusDot>
          </div>
          <div className="hero-value">{fmtPln(accountValue)}</div>
          {totals.tax_pln > 0 && (
            <div className="tag" title="Wartość po 19% podatku od zysków na kontach opodatkowanych, gdyby sprzedać dziś">
              Po podatku: {fmtPln(totals.value_after_tax_pln)} · szac. podatek {fmtPln(totals.tax_pln)}
            </div>
          )}
          <div className="hero-performance">
            <span className={cls(totals.total_pl_pln)}>
              {fmtPln(totals.total_pl_pln)}
              <small> od początku</small>
            </span>
            {latestDaily && (
              <span className={cls(latestDaily.change_pln)}>
                {fmtPln(latestDaily.change_pln)}
                <small> ostatnia sesja</small>
              </span>
            )}
          </div>
          <div className="hero-actions">
            <button className="primary" onClick={() => navigate("activity")}>Dodaj transakcję</button>
            <button className="secondary" onClick={() => run(() => api.refresh(), "Wyceny zostały odświeżone.").catch(() => {})} disabled={busy}>
              {busy ? "Odświeżam…" : "Odśwież wyceny"}
            </button>
          </div>
        </div>

        <div className="summary-stack">
          <Metric
            label="Wynik portfela"
            value={totals.twr == null ? "—" : fmtPct(totals.twr * 100)}
            detail="TWR · bez wpływu wpłat"
            tone={cls(totals.twr)}
          />
          <Metric
            label="Twój wynik"
            value={totals.xirr == null ? "—" : fmtPct(totals.xirr * 100)}
            detail="XIRR · z timingiem wpłat"
            tone={cls(totals.xirr)}
          />
          <Metric
            label="Gotówka"
            value={fmtPln(totals.cash_pln)}
            detail={`${positions.length} ${positions.length === 1 ? "pozycja" : "pozycji"} w portfelu`}
          />
        </div>
      </section>

      <section className="dashboard-grid">
        <div className="surface chart-surface">
          <SectionHeader
            eyebrow="Wynik w czasie"
            title="Portfel vs plan"
            description="Wartość konta wraz z wybranymi punktami odniesienia."
            action={<button className="text-button" onClick={() => navigate("analysis")}>Pełna analiza</button>}
          />
          <HistoryChart data={history} benchmarkRate={benchmarkRate} cpiSpread={cpiSpread} compact />
        </div>

        <aside className="surface allocation-snapshot">
          <SectionHeader
            eyebrow="Struktura"
            title="Portfel"
            action={structureView === "categories"
              ? <button className="text-button" onClick={() => navigate("allocation")}>Szczegóły alokacji</button>
              : <button className="text-button" onClick={() => navigate("portfolio")}>Pełny portfel</button>}
          />
          <div className="structure-toggle" role="group" aria-label="Sposób prezentacji struktury portfela">
            <button className={structureView === "categories" ? "active" : ""} aria-pressed={structureView === "categories"} onClick={() => setStructureView("categories")}>Kategorie</button>
            <button className={structureView === "holdings" ? "active" : ""} aria-pressed={structureView === "holdings"} onClick={() => setStructureView("holdings")}>Walory</button>
          </div>
          {structureView === "categories" ? (
            allocationGroups.length ? (
              <>
                <AllocationDonut groups={allocationGroups} total={allocation?.total_pln} compact />
                {largestDrift && (
                  <div className="insight-line">
                    <span>Największe odchylenie</span>
                    <strong>{largestDrift.category} · {largestDrift.drift_pp > 0 ? "+" : ""}{largestDrift.drift_pp.toFixed(1)} pp</strong>
                  </div>
                )}
              </>
            ) : <EmptyAllocation onOpen={() => navigate("allocation")} />
          ) : (
            <HoldingsStructureChart positions={positions} cashPln={totals.cash_pln} onOpen={openDetail} />
          )}
        </aside>
      </section>

      <section className="surface">
        <SectionHeader
          eyebrow="Aktywa"
          title="Największe pozycje"
          description="Bieżąca wartość, koszt i wynik otwartych inwestycji."
          action={<button className="text-button" onClick={() => navigate("portfolio")}>Zobacz cały portfel</button>}
        />
        <PositionsTable
          positions={positions.slice(0, 5)}
          allPositions={positions}
          totals={totals}
          onOpen={openDetail}
          compact
        />
      </section>
    </>
  );

  const Portfolio = (
    <>
      <div className="metric-grid four">
        <Metric label="Wartość pozycji" value={fmtPln(totals.value_pln ?? totals.value_pln_partial)} detail={`${positions.length} otwartych`} featured />
        <Metric label="Koszt" value={fmtPln(totals.cost_pln)} detail="Kapitał w otwartych pozycjach" />
        <Metric label="Zysk niezrealizowany" value={fmtPln(totals.unrealized_pl_pln)} detail={fmtPct(totals.pl_pct)} tone={cls(totals.unrealized_pl_pln)} />
        <Metric label="Zysk zrealizowany" value={fmtPln(totals.realized_pl_pln)} detail="Zamknięte transakcje" tone={cls(totals.realized_pl_pln)} />
        {totals.tax_pln > 0 && (
          <>
            <Metric label="Podatek przy sprzedaży dziś" value={fmtPln(totals.tax_pln)} detail="Szacunek: 19% zysku na kontach opodatkowanych" />
            <Metric label="Wartość po podatku" value={fmtPln(totals.value_after_tax_pln)} detail="Pozycje i gotówka minus szacowany podatek" />
          </>
        )}
      </div>
      <section className="surface">
        <SectionHeader eyebrow="Pozycje" title="Twój portfel" description="Kliknij instrument, aby zobaczyć historię i źródła wyniku." />
        <PositionsTable positions={positions} totals={totals} onOpen={openDetail} />
      </section>
      <section className="surface">
        <SectionHeader eyebrow="Płynność" title="Konto gotówkowe" description="Wpłaty, wypłaty i środki oczekujące na inwestycję." />
        <CashPanel
          key={account}
          cash={cash}
          accounts={accounts}
          defaultAccount={defaultAccount}
          onAdd={(body) => run(() => api.addCash(body), "Operacja gotówkowa została dodana.").catch(() => {})}
          onDelete={(id) => {
            if (window.confirm("Usunąć tę operację gotówkową?")) {
              run(() => api.deleteCash(id), "Operacja została usunięta.").catch(() => {});
            }
          }}
        />
      </section>
    </>
  );

  const Activity = (
    <>
      <section className="surface">
        <SectionHeader eyebrow="Nowa operacja" title="Dodaj transakcję" description="Wprowadź zakup lub sprzedaż ręcznie." />
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
      </section>
      <section className="surface">
        <SectionHeader eyebrow="Obligacje skarbowe" title="Dodaj obligacje oszczędnościowe" description="EDO, TOS, ROS i ROD — wycena z tabel odsetkowych Ministerstwa Finansów. Wykup dodaj jako sprzedaż." />
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
      </section>
      <section className="surface">
        <SectionHeader
          eyebrow="Historia"
          title="Transakcje"
          description={`${transactions.length} operacji zapisanych w portfelu.`}
          action={<a className="text-button" href="/api/export/transactions.csv">Eksportuj CSV</a>}
        />
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
      </section>
      <section className="surface">
        <SectionHeader
          eyebrow="Dzień po dniu"
          title="Zmiany wartości"
          description="Wynik rynkowy bez traktowania zakupu jako zysku."
          action={<a className="text-button" href="/api/export/daily-changes.csv">Eksportuj dane</a>}
        />
        <DailyChangesTable rows={dailyChanges} />
      </section>
    </>
  );

  const Allocation = (
    <>
      <section className="surface">
        <SectionHeader
          eyebrow="Plan inwestycyjny"
          title="Alokacja docelowa i rzeczywista"
          description="Zobacz, gdzie portfel odchyla się od Twoich założeń i jaka kwota przywróci równowagę."
        />
        <AllocationPanel
          allocation={allocation}
          onSave={(targets) => run(() => api.setAllocation(targets), "Model docelowy został zapisany.").catch(() => {})}
        />
      </section>
      <section className="surface">
        <SectionHeader
          eyebrow="Nowa wpłata"
          title="Rebalancing bez sprzedawania"
          description="Podaj kwotę, a aplikacja podzieli ją między niedoważone klasy aktywów i zachowa docelową gotówkę."
        />
        <RebalancePlanner allocation={allocation} onPlan={(amount) => api.contributionPlan(amount)} />
      </section>
    </>
  );

  const Analysis = (
    <>
      <div className="analysis-view-nav no-print" role="tablist" aria-label="Widok raportów i analizy">
        <button role="tab" aria-selected={analysisView === "report"} className={analysisView === "report" ? "active" : ""} onClick={() => setAnalysisView("report")}>Raport okresowy</button>
        <button role="tab" aria-selected={analysisView === "performance"} className={analysisView === "performance" ? "active" : ""} onClick={() => setAnalysisView("performance")}>Wynik i atrybucja</button>
        <button role="tab" aria-selected={analysisView === "risk"} className={analysisView === "risk" ? "active" : ""} onClick={() => setAnalysisView("risk")}>Ryzyko</button>
        <div className="benchmark-fields">
          <label>Stała stopa <input type="number" step="0.5" value={benchmarkRate} onChange={(e) => setBenchmarkRate(parseFloat(e.target.value) || 0)} />%</label>
          <label>Inflacja + <input type="number" step="0.5" value={cpiSpread} onChange={(e) => setCpiSpread(parseFloat(e.target.value) || 0)} />%</label>
        </div>
      </div>

      {analysisView === "report" && <ReportsPanel key={account} benchmarkRate={benchmarkRate} cpiSpread={cpiSpread} onOpen={openDetail} />}

      {analysisView === "performance" && (
        <div className="analysis-view-content">
          <ReturnsStrip returns={totals.returns} />
          <section className="surface">
            <SectionHeader
              eyebrow="Atrybucja"
              title="Co buduje Twój wynik"
              description="Wynik otwartych i zamkniętych pozycji, klasy aktywów, wpłaty oraz zgodność z planem."
            />
            <AnalyticsBreakdown analytics={analytics} allocation={allocation} onOpen={openDetail} />
          </section>
          <section className="surface">
            <SectionHeader
              eyebrow="Porównanie"
              title="Wartość i stopa zwrotu"
              description="Porównaj wynik portfela ze stałą stopą oraz inflacją."
            />
            <HistoryChart data={history} benchmarkRate={benchmarkRate} cpiSpread={cpiSpread} />
          </section>
        </div>
      )}

      {analysisView === "risk" && (
        <section className="surface">
          <SectionHeader
            eyebrow="Ryzyko"
            title="Obsunięcie od szczytu"
            description="Spadki liczone na indeksie TWR, dlatego wpłaty i wypłaty nie zniekształcają wyniku."
          />
          <DrawdownChart data={drawdown} />
        </section>
      )}
    </>
  );

  const Settings = (
    <>
      <section className="surface">
        <SectionHeader
          eyebrow="Kontrola"
          title="Kondycja danych"
          description="Automatyczna kontrola cen, kursów walut, konfiguracji, alokacji, transakcji i księgi gotówki."
        />
        <DataQualityPanel
          quality={quality}
          busy={busy}
          onRefresh={() => run(() => api.dataQuality(), "Kontrola jakości została odświeżona.").catch(() => {})}
        />
      </section>
      <section className="surface">
        <SectionHeader eyebrow="Synchronizacja" title="Źródła danych" description="Zarządzaj wycenami i danymi potrzebnymi do obliczeń." />
        <div className="sync-grid">
          <div className="sync-item">
            <div>
              <span className="sync-kicker">Wyceny i kursy NBP</span>
              <strong>{latestPriceDate ? `Ostatnie dane: ${latestPriceDate}` : "Brak danych"}</strong>
              <p>Aktualizuje ceny z Yahoo, EODHD lub Alpha Vantage i uzupełnia krótkie luki.</p>
            </div>
            <button className="secondary" disabled={busy} onClick={() => run(() => api.refresh(), "Wyceny zostały odświeżone.").catch(() => {})}>Odśwież</button>
          </div>
          <div className="sync-item">
            <div>
              <span className="sync-kicker">Pełna historia</span>
              <strong>Historia wycen instrumentów</strong>
              <p>Odbudowuje dane potrzebne do wykresów i analizy.</p>
            </div>
            <button className="secondary" disabled={busy} onClick={() => run(() => api.backfill(), "Historia wycen została uzupełniona.").catch(() => {})}>Uzupełnij</button>
          </div>
          <div className="sync-item">
            <div>
              <span className="sync-kicker">Inflacja</span>
              <strong>Eurostat HICP dla Polski</strong>
              <p>Aktualizuje benchmark inflacja + premia.</p>
            </div>
            <button className="secondary" disabled={busy} onClick={() => run(() => api.refreshCpi(), "Dane inflacyjne zostały odświeżone.").catch(() => {})}>Pobierz</button>
          </div>
        </div>
      </section>

      <section className="surface">
        <SectionHeader
          eyebrow="Instrumenty"
          title="Nazwy i mapowanie notowań"
          description="Ticker i kategoria wpływają na wyceny oraz alokację."
        />
        <InstrumentsPanel
          instruments={instruments}
          onSave={(isin, body) => run(() => api.updateInstrument(isin, body), "Ustawienia instrumentu zostały zapisane.")}
        />
      </section>

      <section className="surface">
        <SectionHeader
          eyebrow="Konta"
          title="Konta inwestycyjne"
          description="Każda transakcja i wpłata należy do konta. Dla kont opodatkowanych aplikacja szacuje 19% podatku od zysków; IKE i IKZE zostaw bez podatku. Konto transakcji zmienisz w jej edycji."
        />
        <AccountsPanel
          accounts={accounts}
          busy={busy}
          onSave={(id, body) => run(() => api.saveAccount(id, body), "Konto zostało zapisane.").catch(() => {})}
        />
      </section>

      <section className="surface settings-split">
        <div>
          <SectionHeader eyebrow="Import" title="Import transakcji" description="Obsługuje CSV „historia PW”, eMAKLER „Transakcje bieżące” oraz potwierdzenia PDF mBanku. Format jest rozpoznawany automatycznie." />
          <input ref={fileRef} type="file" accept=".csv,.pdf,application/pdf" className="hidden-file" onChange={onImport} />
          <div style={{ display: "flex", flexWrap: "wrap", gap: 9 }}>
            <AccountSelect accounts={accounts} value={targetImportAccount} onChange={setImportAccount} />
            <button className="secondary" onClick={() => fileRef.current?.click()} disabled={busy}>Wybierz plik CSV lub PDF</button>
          </div>
        </div>
        <div className="settings-divider" />
        <div>
          <SectionHeader eyebrow="Bezpieczeństwo" title="Backup i eksport" description="Pobierz dane lub utwórz kopię na serwerze." />
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
        </div>
      </section>
    </>
  );

  const pages = { overview: Overview, portfolio: Portfolio, activity: Activity, allocation: Allocation, analysis: Analysis, settings: Settings };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <button className="brand" onClick={() => navigate("overview")} aria-label="Przejdź do pulpitu">
          <span className="brand-mark">P</span>
          <span className="brand-copy"><strong>Portfolio</strong><small>personal tracker</small></span>
        </button>
        <nav className="side-nav" aria-label="Główna nawigacja">
          {NAV.map(([id, label, index]) => (
            <button key={id} className={page === id ? "active" : ""} onClick={() => navigate(id)} aria-current={page === id ? "page" : undefined}>
              <span>{index}</span>{label}
              {id === "activity" && transactions.length > 0 && <em>{transactions.length}</em>}
            </button>
          ))}
        </nav>
        <div className="sidebar-foot">
          <StatusDot tone={quality?.status === "good" ? "good" : "warn"}>
            {quality?.status === "error" ? "Błędy danych" : quality?.status === "warning" ? "Sprawdź dane" : "Dane aktualne"}
          </StatusDot>
          <small>Wszystkie wartości w PLN</small>
        </div>
      </aside>

      <main className="main-content">
        <header className="page-header">
          <div>
            <span className="mobile-brand">Portfolio</span>
            <h1>{pageMeta[0]}</h1>
            <p>{pageMeta[1]}</p>
          </div>
          <div className="header-meta">
            {accounts.length > 1 && (
              <select className="cell" aria-label="Widok konta" title="Widok konta" value={account} onChange={(e) => changeAccount(Number(e.target.value))}>
                <option value={0}>Cały portfel</option>
                {accounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
              </select>
            )}
            <span>{new Intl.DateTimeFormat("pl-PL", { day: "numeric", month: "long", year: "numeric" }).format(new Date())}</span>
            <button className="avatar" onClick={() => navigate("settings")} aria-label="Otwórz ustawienia">KP</button>
          </div>
        </header>

        {msg && <div className={`toast ${msg.ok ? "ok" : "err"}`} role="status" aria-live="polite">{msg.text}</div>}
        {busy && <div className="progress-line" aria-label="Trwa aktualizacja" />}

        <div className="page-content">{pages[page]}</div>
      </main>

      <nav className="mobile-nav" aria-label="Nawigacja mobilna">
        {NAV.map(([id, label, index, short]) => (
          <button key={id} className={page === id ? "active" : ""} onClick={() => navigate(id)}>
            <span>{index}</span>{short || label}
          </button>
        ))}
      </nav>

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
