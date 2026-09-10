import type { Metadata } from "next";
import { useCases } from "@/lib/content";
import { Console, TurnLine, WhisperCard } from "@/components/Console";
import Cta from "@/components/Cta";

export const metadata: Metadata = {
  title: "Use cases",
  description:
    "Advisory calls with a spouse present, clinical intake with a caregiver, first notice of loss, and legal intake — anywhere a third voice changes what the record has to prove.",
};

export default function UseCases() {
  return (
    <>
      <section className="hero">
        <div className="wrap">
          <h1>Four rooms where the third voice matters.</h1>
          <p className="lede">
            The common shape: one professional, two or more people who are not, and a record of
            what was said that somebody may later have to defend.
          </p>
        </div>
      </section>

      <section style={{ paddingTop: 0, borderTop: 0 }}>
        <div className="wrap">
          {useCases.map((c, i) => (
            <article className={`case${i % 2 === 1 ? " flip" : ""}`} key={c.title}>
              <div>
                <div className="who">{c.who}</div>
                <h3>{c.title}</h3>
                <p>{c.body}</p>
                <p style={{ marginTop: "1em" }}>
                  <strong>What Second Chair adds.</strong> {c.outcome}
                </p>
              </div>

              <div className="case-visual">
                <Console label="Excerpt">
                  <div className="console-body">
                    <div className="console-room">
                      {c.lines.map((l, j) => (
                        <TurnLine key={j} line={l} />
                      ))}
                      <div style={{ marginTop: 14 }}>
                        <WhisperCard sev={c.whisper.sev} head={c.whisper.head} rule={c.whisper.rule} />
                      </div>
                    </div>
                  </div>
                </Console>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section>
        <div className="wrap record">
          <div className="col-main stack">
            <h2>Where it does not fit</h2>
            <p>
              Second Chair is built for conversations where a professional carries the regulatory
              risk and other people are in the room. It is the wrong tool for a two-party support
              line, for asynchronous transcription, or for anything where the value is a summary
              rather than an intervention.
            </p>
            <p>
              It also assumes speech that can be attributed. A crowded room with overlapping
              voices and no per-speaker microphones will degrade diarization, and every downstream
              stage inherits that.
            </p>
          </div>
          <aside className="margin">
            <h4>Honest scope</h4>
            <p>
              The shipped rule pack covers retail investment advice. The other three rooms are
              demonstrated with the same engine and illustrative rules, not counsel-reviewed packs.
            </p>
            <cite>Rules are a YAML file, replaceable per deployment</cite>
          </aside>
        </div>
      </section>

      <Cta
        title="Try the advisory call"
        body="The demo runs the retail investment scenario end to end — four compliance findings, one redaction, and two moments where the agent is actually asked to speak."
      />
    </>
  );
}
