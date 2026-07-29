import type { Metadata } from "next";
import { QueryPilotDemo } from "./query-pilot-demo";

export const metadata: Metadata = {
  title: "QueryPilot Public Demo",
  description:
    "PostgreSQL planlarını analiz edin; sentetik V2 iş yükü ve regresyon kanıtlarını tarayıcıda inceleyin.",
};

export default function Home() {
  return <QueryPilotDemo />;
}
