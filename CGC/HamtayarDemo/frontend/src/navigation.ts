export const codePages = [
 ['dashboard','نمای کلی کدبیس'],['upload','ورود سورس و پردازش'],['source','مرور کد'],['search','جستجو و تحلیل کد'],['graph','کاوش گراف'],['context','پرسش و کانتکست کد'],['query','گزارش گراف'],['settings','تنظیمات و قابلیت‌ها'],
] as const;
export type CodePage=typeof codePages[number][0];
export function isCodePage(value:unknown):value is CodePage{return codePages.some(([id])=>id===value);}
