import Link from "next/link";
import { DEMO_URL, REPO_URL } from "@/lib/content";
import DemoStatus from "./DemoStatus";

export default function Cta({
  title = "Hear the difference between the two channels",
  body = "The demo runs the full reference call in your browser — no signup, no key. Put headphones on: the earpiece channel is panned left, the room channel sits centre.",
}: {
  title?: string;
  body?: string;
}) {
  return (
    <section>
      <div className="wrap">
        <div className="cta-band">
          <h2>{title}</h2>
          <p>{body}</p>
          <div className="hero-actions">
            <Link className="btn btn-primary" href={DEMO_URL}>
              Run a call
            </Link>
            <a className="btn btn-ghost" href={REPO_URL} target="_blank" rel="noreferrer">
              Read the source
            </a>
            <DemoStatus />
          </div>
        </div>
      </div>
    </section>
  );
}
