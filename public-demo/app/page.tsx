import type { Metadata } from "next";
import { QueryPilotDemo } from "./query-pilot-demo";

export const metadata: Metadata = {
  title: "QueryPilot Public Demo",
  description:
    "PostgreSQL EXPLAIN JSON planlarını tarayıcıda, deterministik kurallarla analiz edin.",
};

export default function Home() {
  return <QueryPilotDemo />;
}
