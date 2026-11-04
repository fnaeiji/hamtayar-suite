import { sampleCodebase } from '../../fixtures/codebase';
export const codebaseService = {
  async runDemo() {
    return { ...sampleCodebase };
  },
};
