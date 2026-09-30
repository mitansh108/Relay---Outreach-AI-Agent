import Image from "next/image";

export default function ProviderLogo({ provider, compact = false }: { provider: "hubspot" | "gmail"; compact?: boolean }) {
  return <span className={`integration-logo ${provider}${compact ? " compact" : ""}`}><Image src={`/logos/${provider}.svg`} alt={provider === "hubspot" ? "HubSpot" : "Gmail"} width={provider === "hubspot" ? 120 : 32} height={provider === "hubspot" ? 32 : 26} unoptimized /></span>;
}
