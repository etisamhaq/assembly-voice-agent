import Link from "next/link";
import { DEMO_URL, REPO_URL } from "@/lib/content";

export default function Footer() {
  return (
    <footer className="site">
      <div className="wrap">
        <div className="foot-grid">
          <div className="foot-brand">
            <Link href="/" className="brand">
              <span className="glyph" aria-hidden="true" />
              Second Chair
            </Link>
            <p>
              A voice agent for conversations with more than two people in them. It warns the
              professional privately, and speaks aloud only when asked.
            </p>
          </div>

          <div className="foot-col">
            <h4>Product</h4>
            <ul>
              <li><Link href="/features">Features</Link></li>
              <li><Link href="/how-it-works">How it works</Link></li>
              <li><Link href="/use-cases">Use cases</Link></li>
              <li><Link href={DEMO_URL}>Demo</Link></li>
            </ul>
          </div>

          <div className="foot-col">
            <h4>Learn</h4>
            <ul>
              <li><Link href="/faq">FAQ</Link></li>
              <li><Link href="/about">About</Link></li>
              <li><a href={REPO_URL} target="_blank" rel="noreferrer">Source code</a></li>
            </ul>
          </div>

          <div className="foot-col">
            <h4>Built with</h4>
            <ul>
              <li><a href="https://www.assemblyai.com/docs/speech-to-text/universal-streaming" target="_blank" rel="noreferrer">AssemblyAI Streaming</a></li>
              <li><a href="https://www.assemblyai.com/docs/llm-gateway/quickstart" target="_blank" rel="noreferrer">AssemblyAI LLM Gateway</a></li>
              <li><a href="https://groq.com" target="_blank" rel="noreferrer">Groq Cloud</a></li>
            </ul>
          </div>
        </div>

        <div className="foot-base">
          <span>&copy; {new Date().getFullYear()} Second Chair</span>
          <span className="disclaimer">
            The shipped rule pack is a demonstration of the mechanism, not a compliance product.
            A real deployment needs rules reviewed by counsel.
          </span>
        </div>
      </div>
    </footer>
  );
}
