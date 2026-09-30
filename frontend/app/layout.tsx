import type { Metadata } from "next";
import "./globals.css";
import "./landing.css";

export const metadata: Metadata = {
  title: "Relay — Sales outreach agents",
  description: "Sales outreach agents that prepare the next action and pause for human review. Connect customer data, review drafts, and approve every send.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
