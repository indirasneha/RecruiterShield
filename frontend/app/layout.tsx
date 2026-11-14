import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "RecruiterShield | Check before you trust",
  description: "Review recruitment messages for common fraud and identity harvesting warning signs.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
