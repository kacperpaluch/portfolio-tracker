import { useState } from "react";
import { fmtPln } from "../format.js";

export default function RebalancePlanner({ allocation, onPlan }) {
  const [amount, setAmount] = useState("5000");
  const [plan, setPlan] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const calculate = async () => {
    const parsed = parseFloat(amount);
    if (!parsed || parsed <= 0) {
      setError("Podaj kwotę większą od zera.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      setPlan(await onPlan(parsed));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="planner-form">
        <label>
          Nowa wpłata
          <div className="planner-input">
            <input className="cell" type="number" min="0" step="100" value={amount} onChange={(e) => setAmount(e.target.value)} onKeyDown={(e) => e.key === "Enter" && calculate()} />
            <span>PLN</span>
          </div>
        </label>
        <button className="primary" disabled={loading || !allocation?.target_complete} onClick={calculate}>
          {loading ? "Obliczam…" : "Zaplanuj wpłatę"}
        </button>
        {!allocation?.target_complete && <span className="tag stale">Najpierw ustaw model sumujący się do 100%.</span>}
      </div>
      {error && <div className="inline-error">{error}</div>}

      {plan && (
        <>
          <div className="planner-summary">
            <div><span>Do zainwestowania</span><strong>{fmtPln(plan.invested_pln)}</strong></div>
            <div><span>Pozostanie w gotówce</span><strong>{fmtPln(plan.reserved_cash_pln)}</strong></div>
            <div><span>Portfel po wpłacie</span><strong>{fmtPln(plan.future_total_pln)}</strong></div>
          </div>
          {plan.recommendations.length ? (
            <div className="recommendations">
              {plan.recommendations.map((item) => (
                <div className="recommendation" key={item.category}>
                  <span className="priority">{String(item.priority).padStart(2, "0")}</span>
                  <div>
                    <strong>{item.category}</strong>
                    <small>
                      {item.candidates.length
                        ? item.candidates.map((c) => c.ticker || c.name).join(" · ")
                        : "Brak skonfigurowanego instrumentu w tej kategorii"}
                    </small>
                  </div>
                  <strong className="pos">+{fmtPln(item.amount_pln)}</strong>
                </div>
              ))}
            </div>
          ) : <div className="quality-empty">Nowa wpłata może pozostać w gotówce zgodnie z planem.</div>}
          <p className="tag">{plan.note} Kwoty są symulacją, nie zleceniem inwestycyjnym.</p>
        </>
      )}
    </div>
  );
}
