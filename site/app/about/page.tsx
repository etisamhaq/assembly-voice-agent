import type { Metadata } from "next";
import { REPO_URL } from "@/lib/content";
import Cta from "@/components/Cta";

export const metadata: Metadata = {
  title: "About",
  description:
    "Why Second Chair exists, the three principles it is built on, and a straight account of where it fits and where it does not.",
};

export default function About() {
  return (
    <>
      <section className="hero">
        <div className="wrap">
          <h1>Built to answer one question.</h1>
          <p className="lede">
            What does a voice agent look like if you stop assuming it is talking to a single
            person wearing a headset?
          </p>
        </div>
      </section>

      <section style={{ paddingTop: 0, borderTop: 0 }}>
        <div className="wrap record">
          <div className="col-main stack">
            <h2>The gap</h2>
            <p>
              Almost every voice agent shipped so far assumes one human and one assistant. The
              assumption is invisible until you put the agent in a room with three people, at
              which point everything built on it stops working. It does not know who spoke. It
              answers questions asked of somebody else. It has no concept of a person who has
              gone quiet.
            </p>
            <p>
              Meanwhile, the conversations where speech carries real legal consequence are almost
              never two-party. An adviser sits with a couple. A clinician sits with a patient and
              their daughter. An adjuster takes a call with a family in the background. In those
              rooms one sentence can create a regulatory problem that nobody notices until the
              recording is reviewed weeks later — long after the moment when saying it differently
              would have cost nothing.
            </p>

            <h2>Three principles</h2>
            <p>
              <strong>Speak last, and rarely.</strong> An agent that answers things nobody asked
              it is worse than no agent, because it takes the professional&rsquo;s attention at
              the exact moment they need it. Second Chair is biased toward silence: across a
              twenty-turn call it speaks aloud twice.
            </p>
            <p>
              <strong>The urgent path cannot depend on the clever one.</strong> A warning about a
              prohibited phrase has to arrive inside the sentence that contained it. That rules
              out a network round trip, so the tier that has to be instant is deterministic and
              local, and the tier that reasons about context runs detached behind it. Neither can
              block the other.
            </p>
            <p>
              <strong>Sensitive data does not get a second chance.</strong> Redaction is the first
              stage of the pipeline rather than a filter at the end. There is no configuration in
              which raw personal data reaches the audit log, the interface, or a language model,
              because there is no code path that carries it there.
            </p>

            <h2>Where it fits</h2>
            <p>
              Second Chair is for regulated advice given out loud, in rooms with more than two
              people, where the record of what was said may later have to be defended. It is not a
              notetaker, and it is deliberately not a general assistant.
            </p>
            <p>
              It assumes speech that can be attributed. A crowded room with overlapping voices and
              no per-speaker microphones will degrade separation, and every stage downstream
              inherits that. It also assumes a rule pack written for your jurisdiction: the packs
              that ship are a working starting point that demonstrates the mechanism, and a real
              deployment replaces them with rules your compliance function has reviewed.
            </p>
          </div>

          <aside className="margin">
            <h4>The name</h4>
            <p>
              Second chair is the junior attorney who sits beside lead counsel. They never run the
              meeting. They always have the answer, and they pass it sideways rather than
              announcing it to the room.
            </p>
            <cite>The whole product is in that description</cite>
            <p style={{ marginTop: "1.4em" }}>
              <a href={REPO_URL} target="_blank" rel="noreferrer">
                Read the source
              </a>
            </p>
          </aside>
        </div>
      </section>

      <Cta />
    </>
  );
}
