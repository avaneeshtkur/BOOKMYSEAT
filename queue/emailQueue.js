const { Queue } = require('bullmq');
const logger = require('../utils/logger');

const connection = {
  host: process.env.REDIS_HOST || '127.0.0.1',
  port: process.env.REDIS_PORT || 6379,
  password: process.env.REDIS_PASSWORD || undefined,
};

const emailQueue = new Queue('email-queue', { connection });

/**
 * Adds an email job to the queue
 * @param {Object} bookingDetails 
 */
async function enqueueEmailJob(bookingDetails) {
  try {
    const job = await emailQueue.add('send-booking-email', bookingDetails, {
      attempts: 3,
      backoff: {
        type: 'fixed',
        delay: 5000, // 5 seconds delay between retries
      },
      removeOnComplete: true,
      removeOnFail: false,
    });

    logger.info(`Email job added to queue`, { 
      jobId: job.id, 
      bookingId: bookingDetails.bookingId,
      email: bookingDetails.email 
    });

    return job;
  } catch (error) {
    logger.error('Failed to add email job to queue', { error: error.message, bookingId: bookingDetails.bookingId });
    throw error;
  }
}

module.exports = {
  emailQueue,
  enqueueEmailJob
};
