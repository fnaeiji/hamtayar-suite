export const workspaces = [
  {
    to: '/documents',
    title: 'پردازش اسناد سازمانی',
    icon: 'documents',
    description: 'اسناد را با مرکز و سطح محرمانگی آماده و ثبت کنید.',
    action: 'ورود به پردازش اسناد',
  },
  {
    to: '/qa',
    title: 'پرسش‌وپاسخ',
    icon: 'qa',
    description: 'پرسش خود را با انتخاب مرکز و سطح دسترسی مطرح کنید.',
    action: 'طرح پرسش',
  },
  {
    to: '/search',
    title: 'جستجو عبارت در اسناد سازمانی',
    icon: 'search',
    description: 'عبارت دلخواه را در متن اسناد ثبت‌شده، با فیلتر فراداده پیدا کنید.',
    action: 'جستجو در اسناد',
  },
  {
    to: '/codebase/dashboard',
    title: 'پردازش کدبیس',
    icon: 'code',
    description: 'سورس، گراف وابستگی، جستجو و کانتکست کد را در همین محیط بررسی کنید.',
    action: 'ورود به همتایار کد',
  },
] as const;
