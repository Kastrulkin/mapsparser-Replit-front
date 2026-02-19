import { useState } from 'react';
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Mail, Phone, MapPin, Loader2 } from "lucide-react";
import Footer from "@/components/Footer";
import { useLanguage } from "@/i18n/LanguageContext";

const Contact = () => {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    phone: '',
    message: ''
  });
  const { t } = useLanguage();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (isSubmitting) return;
    
    setIsSubmitting(true);
    
    try {
      const response = await fetch('/api/public/contact', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
      });
      
      const result = await response.json();
      
      if (response.ok) {
        alert(t.contact.success);
        setFormData({ name: '', email: '', phone: '', message: '' });
      } else {
        throw new Error(result.error || t.contact.error);
      }
    } catch (error) {
      console.error('Ошибка отправки:', error);
      alert(error instanceof Error ? error.message : t.contact.error);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Hero Section */}
      <section className="py-20 px-4 sm:px-6 lg:px-8">
        <div className="max-w-4xl mx-auto text-center">
          <h1 className="text-4xl sm:text-5xl font-bold text-foreground mb-6">
            {t.contact.title}
          </h1>
          <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
            {t.contact.subtitle}
          </p>
        </div>
      </section>

      {/* Contact Form Section */}
      <section className="py-16 px-4 sm:px-6 lg:px-8">
        <div className="max-w-4xl mx-auto">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12">
            {/* Contact Info */}
            <div>
              <h2 className="text-2xl font-bold text-foreground mb-6">{t.contact.contactsTitle}</h2>
              
              <div className="space-y-6">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 bg-primary/10 rounded-full flex items-center justify-center">
                    <Mail className="w-6 h-6 text-primary" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-foreground">{t.contact.emailTitle}</h3>
                    <p className="text-muted-foreground">info@local</p>
                  </div>
                </div>
              </div>
              
              <div className="mt-8 p-6 bg-muted/50 rounded-xl">
                <h3 className="font-semibold text-foreground mb-2">{t.contact.workingHoursTitle}</h3>
                <p className="text-muted-foreground">{t.contact.workingDays1}</p>
                <p className="text-muted-foreground">{t.contact.workingDays2}</p>
              </div>
            </div>

            {/* Contact Form */}
            <Card>
              <CardHeader>
                <CardTitle>{t.contact.formTitle}</CardTitle>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleSubmit} className="space-y-4">
                  <div>
                    <Input
                      name="name"
                      placeholder={t.contact.name}
                      value={formData.name}
                      onChange={handleChange}
                      required
                    />
                  </div>
                  
                  <div>
                    <Input
                      name="email"
                      type="email"
                      placeholder={t.contact.email}
                      value={formData.email}
                      onChange={handleChange}
                      required
                    />
                  </div>
                  
                  <div>
                    <Input
                      name="phone"
                      type="tel"
                      placeholder={t.contact.phone}
                      value={formData.phone}
                      onChange={handleChange}
                    />
                  </div>
                  
                  <div>
                    <Textarea
                      name="message"
                      placeholder={t.contact.message}
                      value={formData.message}
                      onChange={handleChange}
                      rows={4}
                      required
                    />
                  </div>
                  
                  <Button
                    type="submit"
                    size="lg"
                    disabled={isSubmitting}
                    className="w-full"
                  >
                    {isSubmitting ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        {t.contact.sending}
                      </>
                    ) : (
                      t.contact.send
                    )}
                  </Button>
                </form>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      <Footer />
    </div>
  );
};

export default Contact;
