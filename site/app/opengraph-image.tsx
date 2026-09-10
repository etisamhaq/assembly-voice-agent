import { ImageResponse } from "next/og";

export const alt = "Second Chair — the voice agent built for three people in the room";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          background: "#edefea",
          padding: "72px 80px",
          fontFamily: "Georgia, serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
          <div
            style={{
              width: 44,
              height: 44,
              borderRadius: 10,
              background: "#141a16",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 6,
            }}
          >
            <div style={{ width: 5, height: 24, borderRadius: 3, background: "#edefea" }} />
            <div style={{ width: 5, height: 12, borderRadius: 3, background: "#edefea", opacity: 0.55 }} />
          </div>
          <div style={{ fontSize: 34, color: "#141a16", letterSpacing: "-0.02em" }}>Second Chair</div>
        </div>

        <div
          style={{
            display: "flex",
            fontSize: 74,
            lineHeight: 1.06,
            color: "#141a16",
            letterSpacing: "-0.035em",
            maxWidth: 940,
          }}
        >
          Every voice agent assumes two people in the room.
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
          <div style={{ width: 3, height: 46, background: "#2a3f8f" }} />
          <div style={{ display: "flex", fontSize: 27, color: "#3c463f", maxWidth: 900 }}>
            A private warning in the earpiece. A spoken answer only when asked.
          </div>
        </div>
      </div>
    ),
    size,
  );
}
