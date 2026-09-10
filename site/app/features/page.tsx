import type { Metadata } from "next";
import { features, specs } from "@/lib/content";
import Cta from "@/components/Cta";

export const metadata: Metadata = {
  title: "Features",
  description:
    "Two output channels, real-time speaker separation, a 0 ms compliance tier, contextual review, redaction before storage, and an audit record with the regulation cited.",
};

export default function Features() {
  return (
    <>
      <section className="hero">
        <div className="wrap">
          <h1>What it does during the call.</h1>
          <p className="lede">
            Eight capabilities, each of which exists because a conversation with three people in it
            breaks something a two-party voice agent takes for granted.
          </p>
        </div>
      </section>

      <section style={{ paddingTop: 0, borderTop: 0 }}>
        <div className="wrap">
          <div className="featgrid">
            {features.map((f) => (
              <article className="feat" key={f.title}>
                <h3>{f.title}</h3>
                <p>{f.body}</p>
                <span className="cite">{f.cite}</span>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section>
        <div className="wrap record">
          <div className="col-main stack">
            <h2>Under the hood</h2>
            <p>
              Nothing here is a wrapper around a single API call. The ordering of the pipeline is
              the product: redaction first because nothing downstream may see raw personal data,
              the rule tier second because the warning budget is the number that decides whether
              the earpiece is worth wearing, and the model tier detached so it can never delay the
              two stages in front of it.
            </p>
            <table className="spec">
              <tbody>
                {specs.map(([k, v]) => (
                  <tr key={k}>
                    <th scope="row">{k}</th>
                    <td>{v}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <aside className="margin">
            <h4>On the latency budget</h4>
            <p>
              A warning delivered after the sentence has landed is a transcript note, not an
              intervention. The rule tier is held to a hard budget and every breach is counted.
            </p>
            <p>
              Findings from the contextual tier are labelled separately, so a slow review never
              hides a regression in the path that has to be instant.
            </p>
            <cite>0 ms measured, 1000 ms budget, 0 misses</cite>
          </aside>
        </div>
      </section>

      <Cta
        title="See all eight running at once"
        body="The demo plays the full twenty-turn call and shows every warning, every redaction, and the two turns where the agent actually speaks."
      />
    </>
  );
}
