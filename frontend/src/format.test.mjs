// Samosprawdzenie czystych helperów UI: node --test frontend/src/format.test.mjs
// (bez dodatkowych zależności — wbudowany runner Node).
import assert from "node:assert/strict";
import test from "node:test";
import { cls } from "./format.js";
import { paddedDomain } from "./chartTheme.js";

test("cls: zero jest neutralne, nie zielone", () => {
  assert.equal(cls(0), "muted");
  assert.equal(cls(null), "muted");
  assert.equal(cls(0.01), "pos");
  assert.equal(cls(-0.01), "neg");
});

test("paddedDomain: płaska seria dostaje zakres, żeby oś nie powtarzała jednej etykiety", () => {
  const flat = [{ a: 0 }, { a: 0 }, { a: 0 }];
  assert.deepEqual(paddedDomain(flat, ["a"]), [-0.5, 0.5]);

  const spread = [{ a: -3 }, { a: 7 }];
  assert.deepEqual(paddedDomain(spread, ["a"]), ["auto", "auto"]);

  // Brakujące wartości nie mogą wywrócić wyliczenia.
  assert.deepEqual(paddedDomain([{ a: null }], ["a"]), ["auto", "auto"]);
});
