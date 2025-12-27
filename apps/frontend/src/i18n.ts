import { createI18n } from 'vue-i18n'
import en from './locales/en.json'
import zhTw from './locales/zh-tw.json'
import ja from './locales/ja.json'

const i18n = createI18n({
    legacy: false, // use Composition API
    locale: localStorage.getItem('user-locale') || 'en',
    fallbackLocale: 'en',
    messages: {
        en,
        'zh-tw': zhTw,
        ja
    }
})

export default i18n
