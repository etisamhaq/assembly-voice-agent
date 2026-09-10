import Link from "next/link";
import { nav } from "@/lib/content";

export default function NotFound() {
  return (
    <section className="err">
      <div className="wrap">
        <div className="err-in">
          <div className="code">404</div>
          <h1>Nothing on the record at this address.</h1>
          <p className="lede">
            The page you asked for does not exist. It may have been renamed, or the link that sent
            you here may be out of date.
          </p>
          <div className="hero-actions">
            <Link className="btn btn-primary" href="/">
              Back to the home page
            </Link>
            <Link className="btn btn-ghost" href="/how-it-works">
              See how it works
            </Link>
          </div>

          <div className="err-links">
            <span className="note">Everything else on the site:</span>
            <ul>
              {nav.map((item) => (
                <li key={item.href}>
                  <Link href={item.href}>{item.label}</Link>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}
