#!/usr/bin/env node
// 生态箱 M4 验收：存档 → 清空 → 读回 → 接着跑，结果必须与不中断的那一份**逐位相同**。用法：node eco/m4_save_test.js （~1 min）→ results/eco/m4_save_test.json；不相同则退出码 1
//   S1  A 连续跑 600 s；B 跑 300 s → 存成 JSON 字符串 → 丢掉 B → 从字符串读回 → 再跑 300 s：两份状态指纹相同
//   S2  存档字符串再读再存一遍，字符串逐字节相同（存档格式自身稳定）
//   S3  挑战码：导出 → 解析，世界规则 / 种子 / 冠军基因原样回来；拿挑战码开的新局与原局的开局指纹相同
//   S4  坏输入（不是存档、版本太新、挑战码被截断）要报错而不是静默读成别的东西
const fs = require("fs"), path = require("path"), ROOT = path.resolve(__dirname, "..");
const Evolve = require("./evolve.js"), Save = require("./save.js"), Surf = require("./brain_surface.js");
const brain = Surf.create(JSON.parse(fs.readFileSync(path.join(ROOT, "results/eco/brain_surface.json"), "utf8"))), rules = { predators: 3, food: 24, water: 5, size: 180 }, out = { checks: {} };
const A = Evolve.create(rules, { seed: 77, brain }); A.run(600); const fa = Save.fingerprint(A);
let B = Evolve.create(rules, { seed: 77, brain }); B.run(300); const str = JSON.stringify(Save.snapshot(B)); B = null; const B2 = Save.restore(JSON.parse(str), brain); const str2 = JSON.stringify(Save.snapshot(B2)); B2.run(300); const fb = Save.fingerprint(B2);
out.checks.S1_resume_bit_identical = { pass: fa === fb, uninterrupted: fa, resumed: fb, save_bytes: str.length, agents: A.sim.agents.length, births: A.births, lives: A.lives };
out.checks.S2_format_stable = { pass: str === str2 };
const code = Save.challenge(A, "测试挑战"), P = Save.parseChallenge(code), C1 = Evolve.create(P.rules, { seed: P.seed, brain, flight: P.flight }), C0 = Evolve.create(rules, { seed: 77, brain });
const champ = A.hall[0] ? Object.values(Evolve.flat(A.hall[0].genes)).map(v => +v.toFixed(3)) : null, back = P.genes ? Object.values(Evolve.flat(P.genes)) : null;
out.checks.S3_challenge_roundtrip = { pass: Save.fingerprint(C1) === Save.fingerprint(C0) && JSON.stringify(champ) === JSON.stringify(back) && P.note === "测试挑战", code_chars: code.length };
let bad = 0; for (const f of [() => Save.restore({ format: "x" }, brain), () => Save.restore({ format: "fly-ecobox", version: 99 }, brain), () => Save.parseChallenge(code.slice(0, 12) + "!"), () => Save.parseChallenge("hello")]) { try { f(); } catch (e) { bad++; } }
out.checks.S4_bad_input_rejected = { pass: bad === 4, rejected: bad, of: 4 };
out.pass = Object.values(out.checks).every(c => c.pass); fs.writeFileSync(path.join(ROOT, "results/eco/m4_save_test.json"), JSON.stringify(out, null, 1));
for (const [k, c] of Object.entries(out.checks)) console.log(c.pass ? "通过" : "失败", k, JSON.stringify(c)); process.exit(out.pass ? 0 : 1);
