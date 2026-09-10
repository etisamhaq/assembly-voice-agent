import type { Metadata } from "next";
import LiveConsole from "@/components/demo/LiveConsole";
import DemoStatus from "@/components/DemoStatus";
import "./demo.css";

export const metadata: Metadata = {
  title: "Demo",
  description:
    "Run a three-party advisory call in the browser. Watch the transcript get attributed and redacted, the earpiece fire on a prohibited phrase, and the agent stay silent until it is addressed.",
};

export default function DemoPage() {
  return (
    <>
      <section className="hero" style={{ paddingBottom: "clamp(28px, 3vw, 40px)" }}>
        <div className="wrap record">
          <div className="col-main">
            <h1>Run a call.</h1>
            <p className="lede">
              This is the real pipeline, not a recording. Audio is transcribed and attributed,
              every turn is redacted and checked, and the two channels are kept apart end to end.
            </p>
            <div className="hero-actions">
              <DemoStatus />
            </div>
          </div>

          <aside className="margin">
            <h4>Wear headphones</h4>
            <p>
              The earpiece channel is panned hard left and the room channel sits centre. The
              separation is the product, and it is the one part a screenshot cannot show.
            </p>
            <cite>Scripted call needs no microphone permission</cite>
          </aside>
        </div>
      </section>

      <section style={{ paddingTop: 0, borderTop: 0 }}>
        <div className="wrap">
          <LiveConsole />
        </div>
      </section>
    </>
  );
}
