import type { Metadata } from "next";
import { faqs } from "@/lib/content";
import Cta from "@/components/Cta";

export const metadata: Metadata = {
  title: "FAQ",
  description:
    "How Second Chair differs from a notetaker, what the client hears, how fast the warning is, where personal data goes, and what happens when a model is unavailable.",
};

export default function Faq() {
  return (
    <>
      <section className="hero">
        <div className="wrap">
          <h1>Questions worth asking first.</h1>
          <p className="lede">
            Including the ones about latency, privacy and failure that decide whether something
            like this is usable in front of a real client.
          </p>
        </div>
      </section>

      <section style={{ paddingTop: 0, borderTop: 0 }}>
        <div className="wrap record">
          <div className="col-main">
            <div className="faq">
              {faqs.map((f) => (
                <details key={f.q}>
                  <summary>{f.q}</summary>
                  <div className="answer">
                    <p>{f.a}</p>
                  </div>
                </details>
              ))}
            </div>
          </div>

          <aside className="margin">
            <h4>Still unanswered?</h4>
            <p>
              The full pipeline, the rule pack, and the test suite are public. The README covers
              the parts a summary has to leave out.
            </p>
            <p>
              <a href="https://github.com/etisamhaq/assembly-voice-agent" target="_blank" rel="noreferrer">
                Read the source
              </a>
            </p>
          </aside>
        </div>
      </section>

      <Cta
        title="The fastest answer is the demo"
        body="Two minutes in the browser explains more about the two-channel idea than any paragraph here does."
      />
    </>
  );
}
