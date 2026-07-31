export function positionStructureValue(position) {
  const value = position?.value_pln ?? position?.cost_pln ?? 0;
  return Number.isFinite(Number(value)) ? Math.max(0, Number(value)) : 0;
}

export function portfolioStructureTotal(positions, cashPln = 0) {
  const positionsTotal = (positions || []).reduce(
    (sum, position) => sum + positionStructureValue(position),
    0,
  );
  const cash = Number.isFinite(Number(cashPln)) ? Math.max(0, Number(cashPln)) : 0;
  return positionsTotal + cash;
}
