Configuration helpers (Python3 standard library only)

Keep configure_ddr_idf.py beside DDR3_PARAMETERS.csv and check_pll_parameters.py
beside PLL_PARAMETERS.csv, or pass an explicit --csv file. Neither tool invokes
IP Compiler, EDA, network or hardware. No vendor implementation is provided.

DDR workflow
1. In the licensed IP Compiler GUI, create a NEW ddr3_test instance using Logos2
   HMIC_S1.10, PG2L100H / FBG676 / -6. Save the new IDF in a scratch project.
   Close its configuration editor before editing the IDF externally. Keep your
   own backup. Do not point this updater at archived or admitted build inputs.
2. Apply the371 saved name/value pairs to the NEW saved instance:
     python configure_ddr_idf.py work/ddr3_test.idf
   Successful update preserves all XML outside the selected parameter values.
   It stops without writing on model/device/header mismatch, duplicate names,
   missing required fields or unsupported XML serialization. Additional existing
   parameter names remain unchanged. It never creates missing parameters.
3. Reopen that saved IDF with the same licensed GUI. Verify model/device and
   displayed settings, then use Project -> Generate Instance / Generate.
   Do not keep a stale already-open GUI tab that could overwrite the edited IDF.
4. Check the resulting saved IDF after generation:
     python configure_ddr_idf.py work/ddr3_test.idf --check
   Exit0 means371 values match; exit2 STOP identifies a mismatch. The check
   does not prove the generated RTL/source closure corresponds to that IDF.

PLL workflow
Generate cfg_pll (27MHz input /10MHz output0) and bringup_pll (27MHz /148.5MHz)
with the licensed Logos2 PLL GUI, then run:
 python check_pll_parameters.py cfg_pll work/cfg_pll/cfg_pll.v
 python check_pll_parameters.py bringup_pll work/bringup_pll/bringup_pll.v
The checker only reads RTL. It requires the expected module and all saved
localparams, compares numeric literals numerically and quoted strings exactly,
and stops on missing/duplicate/unknown/mismatching parameters or expressions.
An alternative equivalent divider solution is not silently accepted. These
checks do not establish correct primitive wiring, clock frequency or STA;
those need the full generated source-closure and implementation review.

CPU validation used private scratch inputs: changed a saved DDR value then
restored it byte exactly; rejected wrong model version, missing and duplicate
names without writes; checked both frozen wrappers read only; used synthetic
PLL fixtures for mismatch/expression/duplicate/missing rejection. No fresh IP
generation has been run. This is configuration tooling, not fresh-generation
proof or a guarantee of byte-identical generated RTL, ADF or bitstream.
