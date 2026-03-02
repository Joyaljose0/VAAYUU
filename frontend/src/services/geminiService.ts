/// <reference types="vite/client" />
import { GoogleGenerativeAI, SchemaType as Type } from "@google/generative-ai";
import { SensorData, PredictionResult } from "../types";

const genAI = new GoogleGenerativeAI(import.meta.env.VITE_GEMINI_API_KEY || '');

export const analyzeAirQuality = async (
  history: SensorData[],
  current: SensorData
): Promise<PredictionResult> => {
  try {
    const model = genAI.getGenerativeModel({
      model: "gemini-1.5-flash",
      generationConfig: {
        responseMimeType: "application/json",
        responseSchema: {
          type: Type.OBJECT,
          properties: {
            predictedStatus: {
              type: Type.STRING,
              enum: ['SAFE', 'UNSAFE', 'CRITICAL'],
              format: "enum"
            },
            estimatedNextValues: {
              type: Type.OBJECT,
              properties: {
                co2: { type: Type.NUMBER },
                co: { type: Type.NUMBER },
                o2: { type: Type.NUMBER }
              }
            },
            recommendation: { type: Type.STRING },
            confidence: { type: Type.NUMBER }
          },
          required: ["predictedStatus", "estimatedNextValues", "recommendation", "confidence"]
        }
      }
    });

    const result = await model.generateContent(`Analyze this air quality data: 
        Current: ${JSON.stringify(current)}
        History: ${JSON.stringify(history.slice(-5))}`);

    const response = await result.response;
    const text = response.text().trim();
    // Clean potential markdown code blocks if the AI includes them
    const cleanJson = text.startsWith("```json")
      ? text.replace(/^```json\n?/, "").replace(/\n?```$/, "")
      : text;

    return JSON.parse(cleanJson) as PredictionResult;
  } catch (error) {
    console.error("AI Analysis failed. Error:", error);
    try {
      // Attempt to log the raw response if available for debugging
      const result = await (error as any).response;
      if (result) console.error("Raw response text:", result.text());
    } catch (e) { }

    return {
      predictedStatus: 'SAFE',
      estimatedNextValues: { co2: 0, co: 0, o2: 0 },
      recommendation: "Unable to reach AI analysis engine. Relying on local threshold monitoring.",
      confidence: 0
    };
  }
};
