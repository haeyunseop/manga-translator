import type { Metadata, Viewport } from 'next';
import './globals.css';
export const metadata: Metadata = {title:'MangaTrans · 나만의 번역 서재',description:'내 컴퓨터의 AI로 읽는 일본 만화. 개인용 한국어 번역·역식 뷰어.'};
export const viewport: Viewport = {width:'device-width',initialScale:1,themeColor:'#f7f5f0'};
export default function RootLayout({children}:{children:React.ReactNode}) {return <html lang="ko"><body>{children}</body></html>}
