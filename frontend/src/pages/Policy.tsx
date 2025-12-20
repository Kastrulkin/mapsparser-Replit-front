import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import Footer from "@/components/Footer";

const Policy = () => {
  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <Card>
          <CardHeader>
            <CardTitle className="text-3xl font-bold text-center">
              Политика обработки персональных данных
            </CardTitle>
          </CardHeader>
          <CardContent className="prose prose-sm max-w-none">
            <div className="space-y-6 text-foreground">
              <section>
                <h2 className="text-2xl font-semibold mb-4">1. Общие положения</h2>
                <p className="mb-4">
                  Настоящая Политика обработки персональных данных (далее — Политика) определяет порядок обработки 
                  и защиты персональных данных пользователей сервиса BeautyBot.pro (далее — Сервис).
                </p>
                <p>
                  Используя Сервис, вы даёте согласие на обработку ваших персональных данных в соответствии 
                  с настоящей Политикой.
                </p>
              </section>

              <section>
                <h2 className="text-2xl font-semibold mb-4">2. Какие данные мы собираем</h2>
                <p className="mb-4">При использовании Сервиса мы можем собирать следующие персональные данные:</p>
                <ul className="list-disc pl-6 space-y-2">
                  <li>Имя</li>
                  <li>Телефон</li>
                  <li>Адрес</li>
                  <li>Название бизнеса</li>
                  <li>Ссылка на бизнес на картах</li>
                  <li>Telegram ID и username</li>
                </ul>
              </section>

              <section>
                <h2 className="text-2xl font-semibold mb-4">3. Цели обработки данных</h2>
                <p className="mb-4">Персональные данные обрабатываются для следующих целей:</p>
                <ul className="list-disc pl-6 space-y-2">
                  <li>Организация обмена отзывами между участниками сервиса</li>
                  <li>Предоставление доступа к функционалу Сервиса</li>
                  <li>Связь с пользователями по вопросам использования Сервиса</li>
                  <li>Улучшение качества предоставляемых услуг</li>
                </ul>
              </section>

              <section>
                <h2 className="text-2xl font-semibold mb-4">4. Права пользователей</h2>
                <p className="mb-4">Вы имеете право:</p>
                <ul className="list-disc pl-6 space-y-2">
                  <li>Получать информацию о ваших персональных данных</li>
                  <li>Требовать исправления неточных данных</li>
                  <li>Требовать удаления ваших персональных данных</li>
                  <li>Отозвать согласие на обработку персональных данных</li>
                </ul>
              </section>

              <section>
                <h2 className="text-2xl font-semibold mb-4">5. Защита данных</h2>
                <p>
                  Мы принимаем необходимые технические и организационные меры для защиты ваших персональных данных 
                  от неправомерного доступа, изменения, раскрытия или уничтожения.
                </p>
              </section>

              <section>
                <h2 className="text-2xl font-semibold mb-4">6. Контакты</h2>
                <p>
                  По всем вопросам, связанным с обработкой персональных данных, вы можете обращаться через 
                  форму обратной связи на сайте или в Telegram-бот @Beautybotpor_bot.
                </p>
              </section>

              <section className="pt-4 border-t">
                <p className="text-sm text-muted-foreground">
                  Дата последнего обновления: {new Date().toLocaleDateString('ru-RU')}
                </p>
              </section>
            </div>
          </CardContent>
        </Card>
      </div>
      <Footer />
    </div>
  );
};

export default Policy;

