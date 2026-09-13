import Link from "next/link";
import { DEMO_URL, figures, setups, useCases } from "@/lib/content";
import HeroTranscript from "@/components/HeroTranscript";
import DemoStatus from "@/components/DemoStatus";
import Cta from "@/components/Cta";

export default function Home() {
  return (
    <>
      <section className="hero">
        <div className="wrap record">
          <div className="col-main">
            <h1>Every voice agent assumes two people in the room.</h1>
            <p className="lede">
              Second Chair is built for three. It knows who is talking, warns the professional
              privately the moment they cross a regulatory line, and says nothing at all for the
              other ninety percent of the conversation.
            </p>
            <div className="hero-actions">
              <Link className="btn btn-primary" href={DEMO_URL}>
                Run a call
              </Link>
              <Link className="btn btn-ghost" href="/how-it-works">
                See how it works
              </Link>
              <DemoStatus />
            </div>
          </div>

          <aside className="margin">
            <h4>How to read the transcript below</h4>
            <p>
              The left column is the room: everything all three people hear. The right column is
              the advisor&rsquo;s earpiece, and nobody else in the room knows it exists.
            </p>
            <p>
              Watch the gap between a flagged phrase and the warning beside it. That gap is the
              whole product.
            </p>
            <cite>Playing a real excerpt, timed as it happened</cite>
          </aside>
        </div>
      </section>

      <section className="hero-demo">
        <div className="wrap">
          <HeroTranscript />
        </div>
      </section>

      <section>
        <div className="wrap">
          <dl className="figures">
            {figures.map((f) => (
              <div className="figure" key={f.label}>
                <dt>{f.label}</dt>
                <dd>
                  {f.value} <small>{f.unit}</small>
                </dd>
              </div>
            ))}
          </dl>
        </div>
      </section>

      <section>
        <div className="wrap record">
          <div className="col-main stack">
            <h2>In plain terms</h2>
            <p className="plain">
              An adviser is sitting with a couple, talking through a retirement plan. He says
              &ldquo;this one is guaranteed to return eight percent.&rdquo; He didn&rsquo;t mean
              anything by it. It slipped out.
            </p>
            <p className="plain">
              That sentence breaks a rule, and nobody in the room notices. Six weeks later a
              compliance officer finds it in a transcript, and the firm has a problem that costs
              real money.
            </p>
            <p className="plain">
              Second Chair tells him the second he says it, in his earpiece, where only he can
              hear it &mdash; along with the words to put it right. He corrects himself in the
              same breath. The problem never exists.
            </p>
          </div>
          <aside className="margin">
            <h4>Two more things it does</h4>
            <p>
              <strong>It keeps quiet.</strong> It only speaks out loud when someone says its name,
              so it never interrupts the meeting.
            </p>
            <p>
              <strong>It hides private details.</strong> If a client reads out an account number,
              it is erased before it is saved anywhere.
            </p>
          </aside>
        </div>
      </section>

      <section>
        <div className="wrap record">
          <div className="col-main stack">
            <h2>A room is not a headset</h2>
            <p>
              Drop a conventional voice agent into a meeting with three people and it fails in
              three specific ways at once. It cannot tell you who said what, so the transcript is
              useless as a record. It answers questions that were never put to it, because it
              assumes every utterance is addressed to it. And it can only tell you about a problem
              after the call, when the sentence that caused it is already on the recording.
            </p>
            <p>
              Second Chair inverts all three. Speakers are separated as they talk. The agent
              answers only a direct address. And the warning that matters arrives while the
              sentence is still being spoken — early enough to change what comes next.
            </p>
          </div>
          <aside className="margin">
            <h4>Why the margin</h4>
            <p>
              This column is the site&rsquo;s version of the earpiece: the annotation that runs
              alongside the record without interrupting it.
            </p>
            <p>
              In the product it carries the regulation, the severity, and the exact sentence the
              professional can say to correct course.
            </p>
            <cite>FINRA Rule 2210(d)(1)(B)</cite>
          </aside>
        </div>
      </section>

      <section>
        <div className="wrap stack-lg">
          <div className="head-block">
            <h2>Two channels, one agent</h2>
            <p className="lede">
              The whole design follows from a single decision: what the agent says to the
              professional and what it says to the room are different things, carried separately.
            </p>
          </div>

          <div className="diptych">
            <div className="channel private">
              <div className="who-hears">Heard by one person</div>
              <h3>The whisper channel</h3>
              <p>
                Compliance warnings, coaching, and the phrasing to recover. It fires on a
                deterministic rule tier that measures 0 ms, so it lands while the professional is
                still mid-sentence. The client never knows it happened.
              </p>
            </div>
            <div className="channel">
              <div className="who-hears">Heard by everyone</div>
              <h3>The room channel</h3>
              <p>
                Spoken answers, drawn from the client record. It opens its mouth only when someone
                addresses it by name — twice across a twenty-turn call — and treats being mentioned
                in the third person as conversation, not a summons.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section>
        <div className="wrap stack-lg">
          <div className="head-block">
            <h2>Three ways to run it</h2>
            <p className="lede">
              The earpiece is the version people remember, but it is not the only one. Pick
              whichever matches where your conversations already happen.
            </p>
          </div>

          <div className="setups">
            {setups.map((s) => (
              <article className="setup" key={s.name}>
                <h3>{s.name}</h3>
                <p className="effort">{s.effort}</p>
                <p>{s.body}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section>
        <div className="wrap stack-lg">
          <div className="head-block">
            <h2>Where a third voice changes the stakes</h2>
            <p className="lede">
              The pattern repeats anywhere a professional advises two people at once and the record
              of what was said carries legal weight.
            </p>
          </div>

          <ul className="rulelist">
            {useCases.map((c) => (
              <li key={c.title}>
                <span className="idx" aria-hidden="true">
                  ·
                </span>
                <div>
                  <h3>{c.title}</h3>
                  <p>{c.body}</p>
                </div>
              </li>
            ))}
          </ul>

          <Link className="btn btn-ghost" href="/use-cases">
            Read the use cases in full
          </Link>
        </div>
      </section>

      <Cta />
    </>
  );
}
