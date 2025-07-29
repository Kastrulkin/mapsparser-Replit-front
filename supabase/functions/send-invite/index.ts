import { serve } from "https://deno.land/std@0.168.0/http/server.ts"
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}

serve(async (req) => {
  // Handle CORS preflight requests
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders })
  }

  try {
    const { friendEmail, friendUrl, inviterEmail } = await req.json()

    // Create Supabase client
    const supabaseClient = createClient(
      Deno.env.get('SUPABASE_URL') ?? '',
      Deno.env.get('SUPABASE_ANON_KEY') ?? ''
    )

    // Create beautiful HTML email
    const htmlContent = `
      <!DOCTYPE html>
      <html>
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Вас пригласили получить SEO анализ!</title>
        <style>
          body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f8f9fa;
          }
          .container {
            background: white;
            border-radius: 12px;
            padding: 40px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
          }
          .header {
            text-align: center;
            margin-bottom: 30px;
          }
          .logo {
            font-size: 28px;
            font-weight: bold;
            color: #f97316;
            margin-bottom: 10px;
          }
          .title {
            font-size: 24px;
            font-weight: bold;
            color: #1f2937;
            margin-bottom: 10px;
          }
          .subtitle {
            color: #6b7280;
            font-size: 16px;
          }
          .invite-card {
            background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
            border-left: 4px solid #f59e0b;
          }
          .friend-info {
            background: #f3f4f6;
            border-radius: 8px;
            padding: 15px;
            margin: 15px 0;
          }
          .cta-button {
            display: inline-block;
            background: linear-gradient(135deg, #f97316 0%, #ea580c 100%);
            color: white;
            text-decoration: none;
            padding: 16px 32px;
            border-radius: 8px;
            font-weight: bold;
            font-size: 16px;
            margin: 20px 0;
            text-align: center;
          }
          .footer {
            text-align: center;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #e5e7eb;
            color: #6b7280;
            font-size: 14px;
          }
          .highlight {
            color: #f97316;
            font-weight: bold;
          }
        </style>
      </head>
      <body>
        <div class="container">
          <div class="header">
            <div class="logo">BeautyBot</div>
            <div class="title">Вас пригласили! 🎉</div>
            <div class="subtitle">Получите бесплатный SEO анализ вашего бизнеса</div>
          </div>

          <div class="invite-card">
            <p><strong>${inviterEmail}</strong> приглашает вас получить персональный SEO анализ вашего бизнеса на Яндекс.Картах.</p>
          </div>

          <div class="friend-info">
            <p><strong>Ваш email:</strong> ${friendEmail}</p>
            <p><strong>Ссылка на бизнес:</strong> ${friendUrl}</p>
          </div>

          <p>Мы проанализируем вашу карточку организации и дадим рекомендации по улучшению позиций в поиске.</p>

          <div style="text-align: center;">
            <a href="${Deno.env.get('SITE_URL')}/invite?email=${encodeURIComponent(friendEmail)}&url=${encodeURIComponent(friendUrl)}" class="cta-button">
              Принять приглашение
            </a>
          </div>

          <div class="footer">
            <p>Это приглашение от вашего друга. BeautyBot - ИИ-помощник для салонов красоты и локального бизнеса.</p>
            <p>Если вы не ожидали это письмо, просто проигнорируйте его.</p>
          </div>
        </div>
      </body>
      </html>
    `

    // Log for debugging
    console.log('Sending email to:', friendEmail);
    console.log('SITE_URL:', Deno.env.get('SITE_URL'));
    
    // Send email using Supabase Auth API
    const { data, error } = await supabaseClient.auth.admin.sendRawEmail({
      to: friendEmail,
      subject: 'Вас пригласили получить SEO анализ! 🎉',
      html: htmlContent,
      from: 'noreply@beautybot.pro'
    })

    if (error) {
      console.error('Email sending error:', error);
      throw error
    }

    console.log('Email sent successfully:', data);

    return new Response(
      JSON.stringify({ success: true, message: 'Invitation email sent successfully' }),
      { 
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        status: 200 
      }
    )

  } catch (error) {
    return new Response(
      JSON.stringify({ error: error.message }),
      { 
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        status: 400 
      }
    )
  }
}) 