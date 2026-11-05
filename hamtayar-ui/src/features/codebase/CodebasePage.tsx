import { useEffect, useRef } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { codePages, isCodePage } from './navigation';
/** Same-origin, isolated styles; original CGC UI remains the only implementation. */
export function CodebasePage() {
  const { view } = useParams();
  const page = isCodePage(view) ? view : 'dashboard';
  const frame = useRef<HTMLIFrameElement>(null);
  const selected = useRef(page);
  selected.current = page;
  const navigate = useNavigate();
  function send() {
    frame.current?.contentWindow?.postMessage(
      { type: 'hamtayar:code:navigate', page: selected.current },
      window.location.origin,
    );
  }
  useEffect(() => {
    send();
  }, [page]);
  useEffect(() => {
    const receive = (event: MessageEvent) => {
      if (
        event.origin !== window.location.origin ||
        event.source !== frame.current?.contentWindow
      )
        return;
      if (event.data?.type === 'hamtayar:code:ready') send();
      if (
        event.data?.type === 'hamtayar:code:page' &&
        isCodePage(event.data?.page) &&
        event.data.page !== selected.current
      )
        navigate('/codebase/' + event.data.page, { replace: true });
    };
    window.addEventListener('message', receive);
    return () => window.removeEventListener('message', receive);
  }, [navigate]);
  return (
    <section className="page-content code-workspace">
      <p className="eyebrow">
        همتایار کد · {codePages.find(([key]) => key === page)?.[1]}
      </p>
      <h1>پردازش کدبیس</h1>
      <p className="notice">
        ابزار واقعی پردازش کد؛ برای ایندکس، گراف و مدل، سرویس محلی کد و تنظیمات CGC/Neo4j
        باید آماده باشند. انتخاب حالت نمایشی اسناد بر این بخش اعمال نمی‌شود.
      </p>
      <iframe
        ref={frame}
        title="همتایار کد — پردازش کدبیس"
        src="/code/index.html?embedded=1"
        onLoad={send}
      />
    </section>
  );
}
