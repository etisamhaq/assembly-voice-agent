import type { Metadata } from "next";
import { REPO_URL } from "@/lib/content";
import Cta from "@/components/Cta";

export const metadata: Metadata = {
  title: "About",
  description:
    "Why Second Chair exists, what was actually built, and an honest account of what it is not — a hackathon project for the AssemblyAI Voice Agent Hackathon.",
};

export default function About() {
  return (
    <>
      <section className="hero">
        <div className="wrap">
          <h1>Built to answer one question.</h1>
          <p className="lede">
            What does a voice agent look like if you stop assuming it is talking to a single person
            wearing a headset?
          </p>
        </div>
      </section>

      <section style={{ paddingTop: 0, borderTop: 0 }}>
        <div className="wrap record">
          <div className="col-main stack">
            <h2>The gap</h2>
            <p>
              Almost every voice agent shipped so far assumes one human and one assistant. That
              assumption is invisible until you put the agent in a room with three people, at which
              point everything built on it stops working. It does not know who spoke. It answers
              questions asked of somebody else. It has no concept of a person who has gone quiet.
            </p>
            <p>
              Meanwhile, the conversations where speech actually carries legal consequence are
              almost never two-party. An adviser sits with a couple. A clinician sits with a
              patient and their daughter. An adjuster takes a call with a family in the background.
              In those rooms, one sentence can create a regulatory problem that nobody notices
              until the recording is reviewed weeks later.
            </p>

            <h2>What was built</h2>
            <p>
              A working pipeline, not a mockup. Live audio is transcribed and diarized by
              AssemblyAI&rsquo;s streaming API. Every finalised turn is redacted, checked against a
              FINRA and SEC rule pack in under a millisecond, and — in parallel — reviewed by a
              language model that can see the conversation so far. Warnings go to a private channel.
              Answers go to the room, but only when the agent is addressed by name. Everything is
              written to an append-only, personally-identifiable-information-free audit log with the
              regulation cited beside each finding.
            </p>
            <p>
              It is covered by 130 automated tests that require no network access, because the
              scripted call source emits exactly the same objects the live transcription source
              does. The demo you can open is that system running, not a recording of it.
            </p>

            <h2>What it is not</h2>
            <p>
              This is a hackathon build and it is worth being precise about the edges. The client
              record the agent answers from is a fixture, not a CRM integration. The nine shipped
              rules are a credible starting point written to demonstrate the mechanism — a real
              deployment needs a pack reviewed by counsel. Live microphone mode assumes a single
              shared room microphone; per-speaker channels would give cleaner separation. And the
              demo runs on a free container that sleeps between visits.
            </p>
            <p>
              None of that changes the part worth judging: the two-channel model, the ordering of
              the pipeline, and the decision to stay silent by default.
            </p>
          </div>

          <aside className="margin">
            <h4>The name</h4>
            <p>
              Second chair is the junior attorney who sits beside lead counsel. They never run the
              meeting. They always have the answer, and they pass it sideways rather than
              announcing it.
            </p>
            <cite>Built for the AssemblyAI Voice Agent Hackathon</cite>
            <p style={{ marginTop: "1.2em" }}>
              <a href={REPO_URL} target="_blank" rel="noreferrer">
                Source on GitHub
              </a>
            </p>
          </aside>
        </div>
      </section>

      <Cta />
    </>
  );
}
