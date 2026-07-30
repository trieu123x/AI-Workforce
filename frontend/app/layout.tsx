import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Workforce — Enterprise Multi-Agent Platform",
  description:
    "Nền tảng quản lý doanh nghiệp với AI Employees tự động hóa HR, Legal, IT, Finance, Sales và Knowledge.",
  keywords: ["AI", "Enterprise", "Multi-Agent", "HR AI", "Legal AI", "IT AI"],
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="vi" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        {children}
      </body>
    </html>
  );
}
