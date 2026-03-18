const nodemailer = require('nodemailer');
const fs = require('fs');
const path = require('path');
const handlebars = require('handlebars');
const logger = require('../utils/logger');

class EmailService {
  constructor() {
    this.transporter = nodemailer.createTransport({
      host: process.env.SMTP_HOST || 'smtp.gmail.com',
      port: process.env.SMTP_PORT || 587,
      secure: process.env.SMTP_SECURE === 'true', // true for 465, false for other ports
      auth: {
        user: process.env.SMTP_USER,
        pass: process.env.SMTP_PASS,
      },
    });

    this.templateCache = {};
  }

  /**
   * Loads and compiles a Handlebars template
   * @param {string} templateName - The name of the template file (without .hbs)
   * @returns {function} - Compiled Handlebars template function
   */
  getTemplate(templateName) {
    if (this.templateCache[templateName]) {
      return this.templateCache[templateName];
    }

    try {
      const templatePath = path.join(__dirname, '..', 'templates', `${templateName}.hbs`);
      const templateSource = fs.readFileSync(templatePath, 'utf8');
      const compiledTemplate = handlebars.compile(templateSource);
      
      this.templateCache[templateName] = compiledTemplate;
      return compiledTemplate;
    } catch (error) {
      logger.error(`Failed to load email template: ${templateName}`, { error: error.message });
      throw new Error(`Template ${templateName} not found`);
    }
  }

  /**
   * Sends an email using a Handlebars template
   * @param {Object} options - Email options
   * @param {string} options.to - Recipient email address
   * @param {string} options.subject - Email subject
   * @param {string} options.template - Template name to use
   * @param {Object} options.context - Data to inject into the template
   * @returns {Promise<Object>} - Nodemailer info object
   */
  async sendTemplateEmail({ to, subject, template, context }) {
    try {
      const compiledTemplate = this.getTemplate(template);
      const htmlContent = compiledTemplate(context);

      const mailOptions = {
        from: `"BookMySeat Tickets" <${process.env.SMTP_FROM || process.env.SMTP_USER}>`,
        to,
        subject,
        html: htmlContent,
      };

      const info = await this.transporter.sendMail(mailOptions);
      logger.info(`Email sent successfully to ${to}`, { messageId: info.messageId });
      
      return info;
    } catch (error) {
      logger.error(`Error sending email to ${to}`, { error: error.message });
      throw error;
    }
  }
}

module.exports = new EmailService();
