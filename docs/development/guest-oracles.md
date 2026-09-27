# Guest-oracle semantics and PASS boundaries

This is the repository-level contract for interpreting established guest regression oracles. The fixture READMEs remain the authority for their exact records and run procedures. This document defines what their PASS states can support in later missions.

**An oracle PASS proves only the propositions explicitly assigned to that oracle. Do not widen it by implication.** A visible DOS prompt does not establish that FMP playback finished; an FMP screen does not establish continuous audio; a Windows desktop does not establish this fixture's final state; a correct N3 DMA buffer does not establish physical bus timing; and a successful guest boot does not establish correct timer semantics.

## Vocabulary

| Term | Meaning |
| --- | --- |
| `INTEGRATION_ORACLE` | A larger guest environment reached a specified working state. It does not isolate a component's correctness. |
| `ARCHITECTURAL_ASSERTION` | A CPU architectural proposition with an identified architectural authority. |
| `LEGACY_REGRESSION_ASSERTION` | A proposition that pins this emulator's established behavior without claiming physical PC-98 truth. |
| `DEVICE_RELATIONAL_ASSERTION` | An observed ordering or progression relationship, without an exact physical time constant. |
| `HARDWARE_QUALIFIED_ASSERTION` | A proposition backed by suitable physical hardware authority or controlled measurement. Reserve this label for evidence that actually qualifies it. |
| `VISUAL_CHECKPOINT` | A machine-recognizable screen state. It does not automatically prove hidden audio, timing, or internal state. |

One oracle can contain multiple kinds of assertion. These terms summarize existing evidence; they do not rename fixture record types. In particular, the N1 README's `ARCHITECTURAL_CPU_ASSERTION` and N2 README's `CPU_ARCHITECTURAL_REQUIREMENT` are architectural assertions here. Their legacy emulator/backend regression labels fall under `LEGACY_REGRESSION_ASSERTION`. None of the established oracles below is thereby assigned `HARDWARE_QUALIFIED_ASSERTION`.

## FMP command and playback: owner authority

**`fmp s` starts FMP, leaves it resident, and begins playing “Theme of FMP.” The command itself finishes almost immediately. Control returns to the DOS prompt while the music continues playing in the background. Prompt return means FMP command execution completed; it does not mean music playback completed.** This playback timeline is owner-established project knowledge, distinct from what the visual oracle alone can observe.

| Phase | What it means |
| --- | --- |
| `FMP_COMMAND_ISSUED` | The guest has issued `fmp s`; successful execution and playback have yet to be established. |
| `DOS_PROMPT_RETURNED` | The command has returned control to DOS. Background playback can still be active. |
| `BACKGROUND_PLAYBACK_ACTIVE` | “Theme of FMP” is playing after command return. A visual prompt alone does not measure this phase. |
| `POST_PLAYBACK_SETTLED` | A test that requires finished playback has explicitly waited for a post-playback condition. This phase cannot be inferred from `DOS_PROMPT_RETURNED`. |

In the known fixture, a conservative wait of approximately **10 seconds after prompt return** is sufficient for the sample playback to have finished. This is a practical test allowance, **not** an authoritative exact song duration or an existing visual-oracle PASS criterion. A future test that needs finished playback must explicitly wait for the post-playback condition; prompt return alone is insufficient.

The established DOS/FMP screen checkpoint supports bounded command, residency, and visible FMP/YM2608 integration. It does **not** by itself prove playback completion, waveform correctness, FM synthesis phase correctness, PCM correctness, continuous audio delivery, absence of dropouts, host-audio latency, or timer/IRQ timing equivalence to physical PC-98 hardware. Do not report that visual PASS as an audio PASS.

## Stock integration oracles

These are `INTEGRATION_ORACLE`s with `VISUAL_CHECKPOINT`s. A checkpoint is evidence for the listed guest state, within the known fixture and backend, rather than a general component qualification.

| Oracle | PASS supports | PASS does not support |
| --- | --- | --- |
| Stock i286 DOS/FMP | The i286 backend boots the known DOS floppy to the expected triple `A:\>` ready state; command injection works; `fmp s` launches FMP and reaches the expected visible FMP, Theme of FMP, and YM2608 state. | Isolated PIT/PIC/DMA/OPNA timing correctness, waveform or audio continuity, playback completion, or physical PC-98 timing equivalence. |
| Stock IA-32 DOS/VEM486/FMP | The known HDD environment boots through the selected IA-32 backend; its VEM486-containing DOS environment remains integration-compatible; injected commands launch FMP and reach its expected visible state. | Isolated V86, timer, or device timing correctness; waveform/audio correctness; or playback completion from prompt return. |

The i286 oracle uses a floppy DOS ready checkpoint with three `A:\>` prompts before `cd fmutil` and `fmp s`. The IA-32 oracle follows its known HDD boot menu and DOS/VEM486 path before `J:`, `cd fmutil`, and `fmp s`. Their visual comparisons do not analyze the audio signal. The general [time-domain notes](time-domains.md) also treat these screens as integration evidence, not PCM/audio fidelity evidence.

### Stock IA-32 Windows 95 fixture

This `INTEGRATION_ORACLE` recognizes a fixture-specific sequence of `VISUAL_CHECKPOINT`s:

```text
boot menu -> Windows selection -> four distinct Sound SCSI Card DUAL alerts
          -> one VSC-55 alert -> early desktop -> final IntelliPoint hint state
```

The four SCSI dialog appearances and the VSC-55 dialog are expected behavior of this historical fixture. The automation waits for each dialog to remain visually stable before dismissing it; it then distinguishes the early desktop from the final IntelliPoint hint. The final hint requires **six consecutive visual matches at 0.5-second spacing**. **Early desktop is not final PASS.** The IntelliPoint hint is the completion marker for this fixture, not a generic definition of Windows 95 boot completion. The dialogs do not establish PC-98 hardware semantics. Wallpaper palette appearance, mouse pointer, and taskbar clock are not authoritative timing or state criteria unless separately specified.

## N1: i286 PIT/PIC/interrupt IPL fixture

The canonical N1 fixture is an IPL program without DOS. Its six records and exact checks are specified in [the N1 README](../../tests/guest/i286-time-n1/README.md). N1 PASS is bounded to these assertions:

| ID | Record | Supported proposition | Category |
| --- | --- | --- | --- |
| 1 | `PIT_COUNT_LATCH` | Channel-0 live and latched counts are nonzero; the later mode-0 latch is lower. No exact count or frequency is asserted. | `DEVICE_RELATIONAL_ASSERTION` |
| 2 | `PIC_MASK` | With IRQ0 masked, IRR bit 0 is observed while handler count stays zero. Masked-request persistence on physical hardware remains open. | `LEGACY_REGRESSION_ASSERTION` |
| 3 | `PIT_IRQ_EOI` | After unmask/rearm, IRQ0 is pending with IF=0; a handler runs after STI; ISR bit 0 is set on entry and clears after EOI. | `DEVICE_RELATIONAL_ASSERTION` in this emulator |
| 4 | `HLT_WAKE` | No IRQ0 request is pending before `STI; HLT`; the handler's saved IP is immediately after HLT; pre-HLT and post-HLT markers establish wake and continuation. | `LEGACY_REGRESSION_ASSERTION` |
| 5 | `STI_SHADOW` | A pending IRQ is accepted after the instruction following STI; the handler sees the marker change and saved IP after that instruction. | `ARCHITECTURAL_ASSERTION` |
| 6 | `MOV_SS_SHADOW` | A pending IRQ is accepted after `STI; MOV SS,AX; MOV SP,1800h`, with saved IP after MOV SP and the new stack (`entry SP=17F8h`). | `ARCHITECTURAL_ASSERTION` |

The CPU shadow assertions have architectural authority as identified by the fixture README. N1 does not qualify a physical PIT frequency, latch fraction, PIC wiring, or other unresolved physical PC-98 PIT/PIC behavior.

## N2: i286 long-REP IPL fixture

The canonical N2 IPL exercises a 32 KiB `REP MOVSB` under PIT IRQ0 stimulus. [The N2 README](../../tests/guest/i286-time-n2/README.md) defines the three record checks:

| ID | Record | Supported proposition | Category |
| --- | --- | --- | --- |
| 1 | `IRQ_DURING_REP` | IRR is clear before REP; IRQ0 enters PIC service; exactly one handler runs during REP before completion; EOI clears ISR bit 0. | `LEGACY_REGRESSION_ASSERTION`, `DEVICE_RELATIONAL_ASSERTION` |
| 2 | `RESTART_STATE` | The first handler observes partial progress (`0<CX<8000h`, coherent SI/DI), saved IP at the REP prefix, IF set, and DF clear. | `ARCHITECTURAL_ASSERTION` |
| 3 | `FINAL_INTEGRITY` | After IRET and REP completion, CX=0 and SI=DI=`8100h`; all 32 KiB match exactly, expected checksums hold, and guards survive. | `ARCHITECTURAL_ASSERTION` |

N2 establishes mid-REP interrupt, restart, resume, and exact transfer integrity for this case. `REP INS/OUTS` remains deferred because a safe canonical I/O contract is lacking. `CPU_REMCLOCK`, yield count, and overshoot are not guest-visible N2 PASS criteria. N2 does not prove a numerical scheduler-latency bound or exact physical PIT timing.

## N3: i286 direct FDC/DMA IPL fixture

The canonical N3 IPL loads stage2 during bootstrap; **stage2 qualification uses no BIOS disk reads**. It programs the direct FDC command path and DMA channel 2 for two known sectors. [The N3 README](../../tests/guest/i286-time-n3/README.md) defines its two records:

| ID | Record | Supported proposition | Category |
| --- | --- | --- | --- |
| 1 | `DIRECT_READ_S7` | Direct sector-7 read, DMA setup and address/count progression, terminal-count read/clear, result phase, IRQ11/PIC/EOI, and exact known-sector RAM/CRC result. | `LEGACY_REGRESSION_ASSERTION`, `DEVICE_RELATIONAL_ASSERTION` |
| 2 | `FOLLOWUP_READ_S8` | The same chain succeeds for distinct sector 8 and a different destination after the first result/EOI, establishing path reuse. | `LEGACY_REGRESSION_ASSERTION`, `DEVICE_RELATIONAL_ASSERTION` |

N3 pins the legacy emulator's direct FDC/DMA behavior with relational device assertions. It does not qualify physical motor, head, or rotational timing; DMA bus arbitration; terminal-count edge placement; IRQ electrical or edge/level semantics; or physical PC-98 timing. Bootstrap BIOS loading is separate from the stage2 direct-path assertion.

## Rule for future missions

Read this contract before using an established oracle as a gate. Name the exact proposition a PASS supports and retain its non-claims. Preserve established semantics unless the owner explicitly authorizes revision. When extending an oracle, document both the added positive assertion and its limits, and provide suitable authority before making any hardware-qualified claim.
