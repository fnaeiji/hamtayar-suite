import { sampleAnswer } from '../../fixtures/answers';
import { answerQuestion } from '../../services/api/adapters/hamtayarAdapter';
export const qaService = {
  async runDemo() {
    return { ...sampleAnswer };
  },
  runApi: answerQuestion,
};
