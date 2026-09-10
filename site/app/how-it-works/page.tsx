import type { Metadata } from "next";
import { steps } from "@/lib/content";
import Cta from "@/components/Cta";

export const metadata: Metadata = {
  title: "How it works",
  description:
    "Audio to warning in six stages: streaming transcription, speaker attribution, redaction, the deterministic rule tier, a detached contextual review, and the decision to speak or stay silent.",
};

export default function HowItWorks() {
  return (
    <>
      <section className="hero">
        <div className="wrap">
          <h1>From a spoken sentence to a warning in the ear.</h1>
          <p className="lede">
            Six stages, in a fixed order. The order is not an implementation detail — it is what
            makes the difference between a warning that changes the conversation and a note in a
            transcript nobody reads.
          </p>
        </div>
      </section>

      <section style={{ paddingTop: 0, borderTop: 0 }}>
        <div className="wrap record">
          <div className="col-main">
            <ol className="rulelist">
              {steps.map((s, i) => (
                <li key={s.title}>
                  <span className="idx">{i + 1}</span>
                  <div>
                    <h3>{s.title}</h3>
                    <p>{s.body}</p>
                  </div>
                </li>
              ))}
            </ol>
          </div>

          <aside className="margin">
            <h4>Two tiers, on purpose</h4>
            <p>
              A pattern cannot see an omitted risk disclosure. A language model cannot answer in
              two hundred milliseconds. So both run, and neither blocks the other.
            </p>
            <p>
              The rule tier meets the budget. The model tier adds what patterns structurally
              cannot, and arrives when it arrives.
            </p>
            <cite>Tier 1: 0 ms · Tier 2: 3&ndash;6 s</cite>
          </aside>
        </div>
      </section>

      <section>
        <div className="wrap stack-lg">
          <div className="head-block">
            <h2>What happens when something fails</h2>
            <p className="lede">
              A live conversation cannot be paused while infrastructure recovers, so every
              dependency has a defined answer for being unavailable.
            </p>
          </div>

          <table className="spec">
            <tbody>
              <tr>
                <th scope="row">The language model is rate limited or down</th>
                <td>
                  The call continues. One nuanced finding is lost; the deterministic tier keeps
                  catching every pattern violation with no model involved.
                </td>
              </tr>
              <tr>
                <th scope="row">Speech recognition drops a connection</th>
                <td>
                  Audio frames are buffered and the oldest are discarded rather than letting
                  latency grow without bound. Reconnection resumes the session.
                </td>
              </tr>
              <tr>
                <th scope="row">A speaker is mis-attributed</th>
                <td>
                  Roles are seated by speaking order and can be reassigned during the call. The
                  audit log records the attribution that was in force at the time.
                </td>
              </tr>
              <tr>
                <th scope="row">The agent is unsure it was addressed</th>
                <td>
                  It stays quiet. A missed cue costs one repeated question; a wrong answer in front
                  of a client costs the professional&rsquo;s credibility.
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <Cta
        title="Watch the six stages run"
        body="The demo shows the pipeline end to end, with the measured latency printed beside every warning it produces."
      />
    </>
  );
}
