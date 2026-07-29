import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { headers } from "next/headers";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export async function generateMetadata(): Promise<Metadata> {
  const requestHeaders = await headers();
  const host = requestHeaders.get("host") ?? "localhost:3000";
  const protocol =
    requestHeaders.get("x-forwarded-proto") ??
    (host.startsWith("localhost") ? "http" : "https");
  const imageUrl = `${protocol}://${host}/og-v2.png`;

  return {
    title: {
      default: "QueryPilot Public Demo",
      template: "%s · QueryPilot",
    },
    description:
      "PostgreSQL EXPLAIN planlarını, sentetik iş yükünü ve regresyon kanıtlarını güvenli kurallarla inceleyen offline-first demo.",
    icons: {
      icon: "/favicon.svg",
      shortcut: "/favicon.svg",
    },
    openGraph: {
      title: "QueryPilot Public Demo",
      description:
        "Önce kanıt, sonra öneri. Plan analizi ve V2 regresyon gösterimi.",
      type: "website",
      images: [
        {
          url: imageUrl,
          width: 1536,
          height: 1024,
          alt: "QueryPilot — Önce kanıt, sonra öneri.",
        },
      ],
    },
    twitter: {
      card: "summary_large_image",
      title: "QueryPilot Public Demo",
      description:
        "Önce kanıt, sonra öneri. Plan analizi ve V2 regresyon gösterimi.",
      images: [imageUrl],
    },
  };
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="tr">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        {children}
      </body>
    </html>
  );
}
